/**
 * End-to-end approval flow, through a real browser against a real kernel.
 *
 * This is the one path where a bug means Jarvis either does something
 * destructive unasked, or hangs forever waiting on nobody — so it is worth
 * driving for real rather than asserting on units.
 */

import { chromium } from "playwright";
import assert from "node:assert/strict";

const WEB = process.env.WEB_URL ?? "http://localhost:3000";
const API = process.env.API_URL ?? "http://localhost:8000";
const BROWSER = process.env.CHROMIUM_PATH ?? "/opt/pw-browsers/chromium";

const browser = await chromium.launch({ executablePath: BROWSER });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const consoleErrors = [];
page.on("pageerror", (e) => consoleErrors.push(String(e)));
page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));

let failed = 0;
const check = async (name, fn) => {
  try {
    await fn();
    console.log(`  ✓ ${name}`);
  } catch (error) {
    failed += 1;
    console.log(`  ✗ ${name}\n    ${error.message}`);
  }
};

const invoke = (tool, args) =>
  fetch(`${API}/v1/tools/${tool}/invoke`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ arguments: args }),
  });

await page.goto(WEB, { waitUntil: "networkidle" });
await page.waitForTimeout(1000);

await check("a safe tool runs without asking anyone", async () => {
  const response = await invoke("list_files", {});
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.ok(Array.isArray(body.result));
});

await check("a dangerous tool parks and the gate appears with the exact command", async () => {
  // Fire and do not await: this request stays open until a human decides.
  const pending = invoke("run_command", { command: "echo approved-for-real" });

  const gate = page.locator('[role="alertdialog"]');
  await gate.waitFor({ timeout: 15000 });

  const text = await gate.innerText();
  assert.match(text, /Approval needed/);
  assert.match(text, /run_command/);
  // The gate must show the actual command, not just the tool name.
  assert.match(text, /echo approved-for-real/);

  await page.screenshot({ path: "/tmp/shot-approval.png" });

  // Approve, and the parked call completes.
  await page.locator('button[aria-label="Approve"]').click();
  const response = await pending;
  assert.equal(response.status, 200);

  const body = await response.json();
  assert.match(body.result.stdout, /approved-for-real/);
});

await check("the gate disappears once decided", async () => {
  await page.waitForTimeout(600);
  assert.equal(await page.locator('[role="alertdialog"]').count(), 0);

  const health = await (await fetch(`${API}/health`)).json();
  assert.equal(health.pending_approvals, 0);
});

await check("denial refuses the call rather than running it", async () => {
  const pending = invoke("run_command", { command: "touch should-not-exist.txt" });

  const gate = page.locator('[role="alertdialog"]');
  await gate.waitFor({ timeout: 15000 });
  await page.locator('button[aria-label="Deny"]').click();

  const response = await pending;
  assert.equal(response.status, 403, "a denied tool must not report success");

  const listed = await (await fetch(`${API}/v1/tools/list_files/invoke`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ arguments: {} }),
  })).json();
  const names = listed.result.map((entry) => entry.name);
  assert.ok(!names.includes("should-not-exist.txt"), "the denied command must not have run");
});

await check("the tools page groups tools by blast radius", async () => {
  await page.goto(`${WEB}/tools`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const body = await page.locator("main").innerText();

  assert.match(body, /run_command/);
  assert.match(body, /Needs your explicit approval/i);
  for (const tier of ["safe", "sensitive", "dangerous"]) {
    assert.match(body.toLowerCase(), new RegExp(tier));
  }
});

if (consoleErrors.length) {
  failed += 1;
  console.log(`  ✗ no console errors\n    ${consoleErrors.join("\n    ")}`);
} else {
  console.log("  ✓ no console errors");
}

await browser.close();
console.log(failed ? `\n${failed} check(s) failed` : "\nall checks passed");
process.exit(failed ? 1 : 0);
