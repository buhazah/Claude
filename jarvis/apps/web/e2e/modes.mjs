/**
 * End-to-end modes and documents.
 *
 * The claim under test is that a mode is a real constraint rather than a
 * theme: switching it must change which agents can be reached and which
 * memory is read, and the kernel — not the client — must be what enforces it.
 * So the checks go at the boundary from both sides: through the browser, and
 * straight at the API to prove the client is not the only thing holding it.
 */

import { chromium } from "playwright";
import assert from "node:assert/strict";

const WEB = process.env.WEB_URL ?? "http://localhost:3000";
const API = process.env.API_URL ?? "http://localhost:8000";
const BROWSER = process.env.CHROMIUM_PATH ?? "/opt/pw-browsers/chromium";

const browser = await chromium.launch({ executablePath: BROWSER });
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

const post = (path, body) =>
  fetch(`${API}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });

await check("the kernel publishes what each mode narrows", async () => {
  const body = await (await fetch(`${API}/v1/modes`)).json();
  const modes = Object.fromEntries(body.modes.map((m) => [m.id, m]));

  assert.equal(body.default, "personal");
  assert.ok(modes.coding.agent_count < modes.personal.agent_count);
  assert.ok(!modes.coding.agents.includes("life_coach"));
  assert.equal(modes.business.memory_scope, "business");
});

await check("a mode is enforced by the kernel, not only by the client", async () => {
  // Pinning an excluded agent must fail even though nothing in the UI offered
  // it — otherwise `agent_id` is a way straight around the narrowing.
  const pinned = await post("/v1/chat", {
    message: "hello",
    mode: "coding",
    agent_id: "life_coach",
  });
  assert.equal(pinned.status, 404);
  assert.match((await pinned.json()).detail, /not available in coding mode/);

  // And the same agent is reachable with no mode.
  assert.equal((await post("/v1/chat", { message: "hi", agent_id: "life_coach" })).status, 200);
});

await check("an unknown mode is refused rather than silently defaulted", async () => {
  // Defaulting would fail *open*: the default mode is the unconstrained one.
  const response = await post("/v1/chat", { message: "hello", mode: "busines" });
  assert.equal(response.status, 404);
  assert.match((await response.json()).detail, /unknown mode/);
});

await check("routing preview stays inside the mode", async () => {
  const body = await (
    await post("/v1/route?mode=coding", { message: "I feel anxious about the release" })
  ).json();
  assert.equal(body.mode, "coding");
  assert.ok(
    body.candidates.every((c) => c.agent_id !== "life_coach"),
    `coding mode routed to ${JSON.stringify(body.candidates)}`,
  );
});

await page.goto(WEB, { waitUntil: "networkidle" });
await page.waitForTimeout(900);

await check("the switcher lists modes with what each one costs you", async () => {
  await page.getByTestId("mode-switcher").click();
  const menu = page.locator('[role="listbox"]');
  await menu.waitFor({ timeout: 5000 });

  const text = await menu.innerText();
  assert.match(text, /Personal/);
  assert.match(text, /Coding/);
  // Not just names: the menu says what changes.
  assert.match(text, /agents · coding memory/);
  await page.screenshot({ path: "/tmp/shot-modes.png" });
});

await check("switching mode survives a reload", async () => {
  await page.locator('[role="option"]', { hasText: "Coding" }).click();
  await page.waitForTimeout(300);
  assert.match(await page.getByTestId("mode-switcher").innerText(), /Coding/);

  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  assert.match(await page.getByTestId("mode-switcher").innerText(), /Coding/);
});

await check("the palette previews routing within the selected mode", async () => {
  await page.keyboard.press("Control+K");
  await page.locator('[role="dialog"]').waitFor({ timeout: 5000 });
  await page.keyboard.type("I feel anxious about the release");
  await page.waitForTimeout(1400);

  const shown = await page.locator('[role="dialog"]').innerText();
  assert.ok(!/life coach/i.test(shown), `coding mode offered: ${shown}`);
  await page.keyboard.press("Escape");
});

await check("a document is planned as an outline before any prose", async () => {
  await page.goto(`${WEB}/documents`, { waitUntil: "networkidle" });
  await page.getByTestId("document-request").fill("Review of Q3 revenue and the margin risk");
  await page.getByTestId("compose").click();

  // The outline landing first is the point at which the user can say "no, not
  // that shape" — before the writing has been paid for.
  const outline = page.getByTestId("outline");
  await outline.waitFor({ timeout: 30000 });
  assert.ok((await outline.locator("li").count()) >= 1);

  await page.getByTestId("document-body").waitFor({ timeout: 60000 });
  await page.screenshot({ path: "/tmp/shot-documents.png" });
});

await check("the document is in the library and exports as markdown", async () => {
  const documents = await (await fetch(`${API}/v1/documents`)).json();
  assert.ok(documents.length >= 1, "the composed document must be listed");
  const [document] = documents;
  assert.equal(document.state, "complete");
  assert.ok(document.words > 0);

  const markdown = await fetch(`${API}/v1/documents/${document.id}/export?format=md`);
  assert.equal(markdown.status, 200);
  const text = await markdown.text();
  assert.ok(text.startsWith("# "), "markdown must start with the title");
  assert.match(text, /^## /m, "and carry the section headings");

  const html = await (await fetch(`${API}/v1/documents/${document.id}/export?format=html`)).text();
  assert.ok(html.startsWith("<!doctype html>"));
  // Self-contained: it has to survive being emailed to someone.
  assert.ok(!/https?:\/\//.test(html), "the export must not reference external assets");
});

await check("a document composed in a mode is filed under it", async () => {
  const documents = await (await fetch(`${API}/v1/documents?mode=coding`)).json();
  assert.ok(documents.length >= 1, "the document was composed in coding mode");
  assert.ok(documents.every((d) => d.mode === "coding"));

  assert.deepEqual(await (await fetch(`${API}/v1/documents?mode=business`)).json(), []);
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
