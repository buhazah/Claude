/**
 * End-to-end smoke test.
 *
 * Unit tests cover the SSE parser and API client; this covers the thing they
 * cannot — that a real browser, talking to a real kernel, can route a request,
 * stream an answer, and show the run. Requires both servers to be running:
 *
 *   apps/api $ uvicorn jarvis.main:app          # :8000
 *   apps/web $ pnpm build && pnpm start         # :3000
 */

import { chromium } from "playwright";
import assert from "node:assert/strict";

const WEB = process.env.WEB_URL ?? "http://localhost:3000";
const BROWSER = process.env.CHROMIUM_PATH ?? "/opt/pw-browsers/chromium";

const browser = await chromium.launch({ executablePath: BROWSER });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

const consoleErrors = [];
page.on("console", (message) => message.type() === "error" && consoleErrors.push(message.text()));
page.on("pageerror", (error) => consoleErrors.push(String(error)));

const checks = [];
const check = (name, fn) => checks.push({ name, fn });

check("dashboard reports the kernel as online", async () => {
  await page.goto(WEB, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.locator("text=Online").first().waitFor({ timeout: 5000 });
  const agents = await page.locator("text=/\\d+ agents/").first().innerText();
  assert.match(agents, /\d+ agents/);
});

check("command palette previews routing before executing", async () => {
  await page.keyboard.press("Meta+k");
  await page.locator('input[placeholder*="Tell Jarvis"]').waitFor({ timeout: 5000 });
  await page.locator('input[placeholder*="Tell Jarvis"]').fill("find leads for my supplement brand");
  await page.locator("text=Agents Jarvis would activate").waitFor({ timeout: 5000 });

  const top = await page.locator('[role="dialog"] .w-\\[132px\\]').first().innerText();
  assert.equal(top.trim(), "sales", "lexical routing should pick the sales agent");
});

check("executing streams an answer and records the run", async () => {
  await page.keyboard.press("Enter");
  await page.waitForURL("**/chat**");
  await page.locator("main >> text=/echo:/").waitFor({ timeout: 10000 });

  const transcript = await page.locator("main").innerText();
  assert.match(transcript, /sales/i, "the answering agent should be labelled");
  assert.match(transcript, /tokens/, "usage should be reported");
});

check("live activity shows the kernel's own events", async () => {
  const rail = await page.locator("aside").innerText();
  assert.match(rail, /LIVE ACTIVITY/i);
  assert.match(rail, /sales|routed|model/i, "kernel events should be rendered");
});

check("every section renders", async () => {
  for (const [path, heading] of [
    ["/agents", "Agents"],
    ["/memory", "Memory"],
    ["/runs", "Runs"],
    ["/tools", "Tools"],
  ]) {
    await page.goto(`${WEB}${path}`, { waitUntil: "networkidle" });
    assert.equal((await page.locator("h1").first().innerText()).trim(), heading);
  }
});

check("the run just executed appears in run history", async () => {
  await page.waitForTimeout(500);
  const runs = await page.goto(`${WEB}/runs`, { waitUntil: "networkidle" }).then(async () => {
    await page.waitForTimeout(800);
    return page.locator("main").innerText();
  });
  assert.match(runs, /succeeded/, "the completed run should be listed");
  assert.match(runs, /supplement brand/, "with its original request");
});

let failed = 0;
for (const { name, fn } of checks) {
  try {
    await fn();
    console.log(`  ✓ ${name}`);
  } catch (error) {
    failed += 1;
    console.log(`  ✗ ${name}\n    ${error.message}`);
  }
}

if (consoleErrors.length) {
  failed += 1;
  console.log(`  ✗ no console errors\n    ${consoleErrors.join("\n    ")}`);
} else {
  console.log("  ✓ no console errors");
}

await browser.close();
console.log(failed ? `\n${failed} check(s) failed` : `\n${checks.length + 1} checks passed`);
process.exit(failed ? 1 : 0);
