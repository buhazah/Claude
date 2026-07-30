/**
 * The morning briefing, through a real browser against a real kernel.
 *
 * What is being checked is not that a page renders. It is the two claims the
 * whole subsystem rests on, and both of them are claims about *restraint*:
 *
 *   - every recommendation shows the evidence that produced it, without a
 *     click, because a score you cannot interrogate is one you either believe
 *     blindly or ignore
 *   - the briefing says what it could not see, because a missing calendar
 *     section reads as "nothing on today" rather than "Jarvis cannot see your
 *     calendar"
 *
 * State is seeded through the API first, so the page has something to be
 * proactive about — a briefing on an empty system is correct and proves
 * nothing.
 */

import { launchBrowser } from "./browser.mjs";
import assert from "node:assert/strict";

const WEB = process.env.WEB_URL ?? "http://localhost:3000";
const API = process.env.API_URL ?? "http://localhost:8000";

const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
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

// A scope unique to this run. Recommendation ids are stable across sweeps by
// design — that is what makes "not now" mean anything — so a fixed scope would
// mean the second run of this suite found its own dismissal from the first and
// saw an empty briefing. Correct behaviour; a bad test.
const SCOPE = `e2e-${Date.now()}`;

const remember = (content, kind) =>
  fetch(`${API}/v1/memory`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ content, kind, scope: SCOPE }),
  });

// Three failures in one scope is a process problem, which is a signal the
// engine reports with real evidence attached.
await remember("The Friday deploy broke checkout", "mistake");
await remember("The Tuesday migration lost two orders", "mistake");
await remember("The webhook retry storm double-charged someone", "mistake");

await check("the briefing endpoint assembles without a model", async () => {
  const body = await (await fetch(`${API}/v1/briefing`)).json();
  assert.ok(body.opener, "there must always be an opener");
  assert.equal(body.generated_by, "arithmetic", "no key configured, so no model wrote this");
  assert.ok(body.unavailable.email, "an absent connector must be named");
});

await page.goto(`${WEB}/briefing`, { waitUntil: "networkidle" });
await page.waitForTimeout(600);

await check("the page leads with one sentence, not a list", async () => {
  const main = await page.locator("main").innerText();
  assert.match(main, /Fix the cause: 3 recorded failures/);
  await page.screenshot({ path: "/tmp/shot-briefing.png" });
});

await check("every recommendation shows its evidence without a click", async () => {
  const main = await page.locator("main").innerText();
  assert.match(main, /webhook retry storm double-charged someone/);
  // Case-insensitive: the section label is uppercased in CSS, so innerText
  // returns it in caps.
  assert.match(main, /impact × urgency × confidence/i);
});

await check("what Jarvis could not see is named", async () => {
  const main = await page.locator("main").innerText();
  assert.match(main, /Not covered/);
  assert.match(main, /no mail connector is mounted/);
});

await check("a suggested action can be handed straight back", async () => {
  const link = page.getByRole("link", { name: /Ask chief_of_staff/ }).first();
  await link.waitFor({ timeout: 5000 });
  assert.match(await link.getAttribute("href"), /^\/chat\?q=/);
});

await check("dismissing removes it here and on the server", async () => {
  const before = (await (await fetch(`${API}/v1/recommendations`)).json()).recommendations.length;

  const dismiss = page.getByRole("button", { name: /^Dismiss: Fix the cause/ });
  await dismiss.waitFor({ timeout: 5000 });
  await dismiss.click();
  await page.waitForTimeout(500);

  // The row goes. The *opener* deliberately does not change — it was written
  // for this morning, and a briefing that rewrites itself as you act on it is
  // a feed rather than a briefing.
  assert.equal(await page.getByRole("button", { name: /^Dismiss: Fix the cause/ }).count(), 0);

  const after = (await (await fetch(`${API}/v1/recommendations`)).json()).recommendations.length;
  assert.equal(after, before - 1, "the dismissal must survive a reload, not just a re-render");
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
