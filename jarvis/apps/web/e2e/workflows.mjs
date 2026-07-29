/**
 * Workflows end-to-end.
 *
 * The property under test is the one the milestone exists for: a workflow that
 * needs a human *suspends* — holding nothing open — and continues when the
 * decision arrives, through the ordinary approval surface.
 */

import { launchBrowser } from "./browser.mjs";
import assert from "node:assert/strict";

const WEB = process.env.WEB_URL ?? "http://localhost:3000";
const API = process.env.API_URL ?? "http://localhost:8000";

const browser = await launchBrowser();
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

await page.goto(`${WEB}/workflows`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);

await check("the starter workflows are listed with their steps", async () => {
  const body = await page.locator("main").innerText();
  assert.match(body, /Inbox triage/);
  assert.match(body, /Company brief/);

  await page.getByRole("button", { name: "Inbox triage" }).click();
  await page.waitForTimeout(400);

  const expanded = await page.locator("main").innerText();
  assert.match(expanded, /approval/, "the human-decision step should be visible");
  assert.match(expanded, /branch/);
});

await check("a workflow with no approval runs to completion", async () => {
  const started = await fetch(`${API}/v1/workflows/wfl_weekly_review/run`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ inputs: {} }),
  });
  const run = await started.json();

  assert.equal(run.state, "succeeded");
  assert.equal(run.records.length, 2);
});

await check("a workflow needing a decision suspends without holding a connection", async () => {
  const before = Date.now();
  const started = await fetch(`${API}/v1/workflows/wfl_inbox_triage/run`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ inputs: { body: "Can you send the invoice?", from: "sam@acme.test" } }),
  });
  const run = await started.json();
  const elapsed = Date.now() - before;

  assert.equal(run.state, "awaiting_approval", "it should be parked, not finished");
  assert.ok(elapsed < 20000, "the request returned rather than blocking on a person");
  assert.ok(run.awaiting_approval_id);
});

await check("the approval gate shows the parked workflow", async () => {
  await page.reload({ waitUntil: "networkidle" });
  // Several may be pending from earlier runs; the newest is ours.
  const gate = page.locator('[role="alertdialog"]').first();
  await gate.waitFor({ timeout: 15000 });

  const text = await gate.innerText();
  assert.match(text, /Approval needed/);
  assert.match(text, /workflow:Inbox triage/);
  await page.screenshot({ path: "/tmp/shot-workflow.png" });
});

await check("approving resumes the run to completion", async () => {
  await page.locator('button[aria-label="Approve"]').first().click();

  // The scheduler picks the decision off the bus and resumes the run.
  let finished = null;
  for (let attempt = 0; attempt < 60; attempt += 1) {
    await page.waitForTimeout(250);
    const runs = await (await fetch(`${API}/v1/workflow-runs`)).json();
    finished = runs.find((r) => r.workflow_name === "Inbox triage");
    if (finished && finished.state !== "awaiting_approval") break;
  }

  assert.ok(finished, "the run should be listed");
  assert.equal(finished.state, "succeeded", "an approved workflow should finish");
});

await check("the run history shows how each run was triggered", async () => {
  await page.goto(`${WEB}/workflows`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);

  const body = await page.locator("main").innerText();
  assert.match(body, /recent runs/i);  // rendered uppercase by CSS
  assert.match(body, /manual/);
  assert.match(body, /succeeded/);
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
