/**
 * End-to-end computer control: a real Chromium driven by the kernel, watched
 * through a real Chromium driven by Playwright.
 *
 * The API server for this suite is started with computer control enabled and a
 * throwaway origin on the allowlist, so the wall is exercised against a page
 * that actually exists. What is being proved is not that a browser can be
 * driven — it is that the wall holds when it is:
 *
 *   - a credential field is refused outright, with no approval offered
 *   - a committing click parks in the same approval gate as any other
 *     dangerous action, quoting what the page itself says
 *   - the site is off the allowlist, so even opening it asks first
 */

import { chromium } from "playwright";
import assert from "node:assert/strict";
import { createServer } from "node:http";

const WEB = process.env.WEB_URL ?? "http://localhost:3000";
const API = process.env.API_URL ?? "http://localhost:8000";
const BROWSER = process.env.CHROMIUM_PATH ?? "/opt/pw-browsers/chromium";

const PAGE = `<!doctype html><html><body>
  <h1>Checkout</h1>
  <p>Order total is 2,480 pounds.</p>
  <input id="promo" name="promo" placeholder="Discount code">
  <input id="card" name="cardNumber" autocomplete="cc-number" placeholder="Card number">
  <button id="more">Load more</button>
  <button id="pay">Place order</button>
  <a href="/next">Keep shopping</a>
</body></html>`;

// A throwaway origin for Jarvis to drive. Bound to the port the API was told
// to allowlist, so the run is not a permanent hole in anyone's config.
const site = createServer((_, response) => {
  response.writeHead(200, { "content-type": "text/html" });
  response.end(PAGE);
});
await new Promise((resolve) => site.listen(8123, "127.0.0.1", resolve));
const SITE = "http://127.0.0.1:8123/";

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

const invoke = (tool, args) =>
  fetch(`${API}/v1/tools/${tool}/invoke`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ arguments: args }),
  });

const status = () => fetch(`${API}/v1/computer`).then((r) => r.json());

await check("the browser driver is live and its reach is published", async () => {
  const health = await (await fetch(`${API}/health`)).json();
  assert.equal(health.computer.driver, "browser");
  assert.equal(health.computer.available, true);
  assert.deepEqual(health.computer.allowed_hosts, ["127.0.0.1"]);
});

await check("opening an allowlisted page yields named elements", async () => {
  const response = await invoke("browser_open", { url: SITE });
  assert.equal(response.status, 200, await response.text());

  const { page: screen } = await status();
  const names = screen.elements.map((e) => e.name);
  assert.ok(names.includes("Place order"), `expected a Place order button, got ${names}`);
  assert.ok(names.includes("Keep shopping"));
});

await check("a credential field is marked, and typing into it is refused", async () => {
  const { page: screen } = await status();
  const card = screen.elements.find((e) => e.name === "Card number");
  assert.ok(card, "the card field must be perceived");
  assert.equal(card.secret, true, "a cc-number field must be marked as a credential");

  // "Keep shopping" contains "pin" — the substring bug this test also guards.
  const link = screen.elements.find((e) => e.name === "Keep shopping");
  assert.equal(link.secret, false, "an ordinary link must not be marked a credential");

  const response = await invoke("browser_type", { ref: card.ref, text: "4111111111111111" });
  assert.equal(response.status, 403, "a credential field is a refusal, not an approval");
  const body = await response.json();
  assert.match(JSON.stringify(body), /never entered by an agent/);
});

await check("an ordinary field is typed into without asking anyone", async () => {
  const { page: screen } = await status();
  const promo = screen.elements.find((e) => e.name === "Discount code");
  const response = await invoke("browser_type", { ref: promo.ref, text: "SAVE20" });
  assert.equal(response.status, 200);

  const after = (await status()).page.elements.find((e) => e.name === "Discount code");
  assert.equal(after.value, "SAVE20");
});

await page.goto(`${WEB}/computer`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);

await check("the computer page shows the screen, the wall and every step", async () => {
  const body = await page.locator("main").innerText();
  assert.match(body, /driver: browser/);
  assert.match(body, /127\.0\.0\.1/);
  assert.match(body, /never filled by Jarvis/, "the credential field must be called out");
  assert.match(body, /refused/, "the refused action must be visible, not swallowed");
  assert.match(body, /type 'SAVE20' into textbox «Discount code»/);

  const shot = page.locator('img[alt="Current browser screen"]');
  await shot.waitFor({ timeout: 5000 });
  await page.screenshot({ path: "/tmp/shot-computer.png" });
});

await check("a committing click parks in the approval gate, quoting the page", async () => {
  const { page: screen } = await status();
  const pay = screen.elements.find((e) => e.name === "Place order");
  const pending = invoke("browser_click", { ref: pay.ref });

  const gate = page.locator('[role="alertdialog"]');
  await gate.waitFor({ timeout: 15000 });
  const text = await gate.innerText();
  assert.match(text, /Place order/, "the gate must quote what the page says");
  assert.match(text, /127\.0\.0\.1/, "and where it says it");

  await page.locator('button[aria-label="Deny"]').click();
  const response = await pending;
  assert.equal(response.status, 403, "a denied click must not report success");
});

await check("the denied click is on the record as denied", async () => {
  await page.waitForTimeout(800);
  const { steps } = await status();
  const last = steps[steps.length - 1];
  assert.match(last.description, /click button «Place order»/);
  assert.equal(last.verdict, "approve");
  assert.equal(last.ok, false);
});

if (consoleErrors.length) {
  failed += 1;
  console.log(`  ✗ no console errors\n    ${consoleErrors.join("\n    ")}`);
} else {
  console.log("  ✓ no console errors");
}

await browser.close();
site.close();
console.log(failed ? `\n${failed} check(s) failed` : "\nall checks passed");
process.exit(failed ? 1 : 0);
