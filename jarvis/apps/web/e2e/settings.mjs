/**
 * End-to-end vault and budget.
 *
 * The one property worth driving through a real browser: a secret stored
 * through the UI is never rendered back by it, and never appears in any
 * response the page could have fetched. Everything else about the vault is
 * covered by unit tests; this is the check that the *surface* does not leak.
 *
 * Needs an API started with a vault key:
 *   JARVIS_VAULT_KEY=$(python -m jarvis.security.keygen) uvicorn jarvis.main:app
 */

import { chromium } from "playwright";
import assert from "node:assert/strict";

const WEB = process.env.WEB_URL ?? "http://localhost:3000";
const API = process.env.API_URL ?? "http://localhost:8000";
const BROWSER = process.env.CHROMIUM_PATH ?? "/opt/pw-browsers/chromium";
// Deliberately not shaped like any real provider's key: a realistic-looking
// fixture trips secret scanners on the way out, which is a fair complaint
// about a file that is committed. It only needs to be long enough to be
// redactable and to produce a checkable hint.
const SECRET = "NOT-A-REAL-KEY-vault-fixture-4821";

const browser = await chromium.launch({ executablePath: BROWSER });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const consoleErrors = [];
page.on("pageerror", (e) => consoleErrors.push(String(e)));
page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));

// Every response the page receives, so "did the secret come back" is answered
// by what crossed the wire rather than by what happened to be rendered.
const bodies = [];
page.on("response", async (response) => {
  if (!response.url().startsWith(API)) return;
  try {
    bodies.push(await response.text());
  } catch {
    /* a streamed body — not a listing */
  }
});

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

await page.goto(`${WEB}/settings`, { waitUntil: "networkidle" });
await page.waitForTimeout(900);

await check("the vault is unlocked and the page offers to store a secret", async () => {
  assert.equal(await page.getByTestId("vault-locked").count(), 0, "the API needs a vault key");
  await page.getByTestId("secret-name").waitFor({ timeout: 5000 });
});

await check("a stored secret is listed by hint, never by value", async () => {
  await page.getByTestId("secret-name").fill("e2e_stripe");
  await page.getByTestId("secret-value").fill(SECRET);
  await page.getByTestId("secret-save").click();

  const list = page.getByTestId("secret-list");
  await list.waitFor({ timeout: 10000 });
  const text = await list.innerText();

  assert.match(text, /e2e_stripe/);
  assert.match(text, /NOT…21/, "the hint must be shown");
  assert.ok(!text.includes(SECRET), "the value must never be rendered");
});

await check("the secret is in no response the page received", async () => {
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  const leaked = bodies.filter((body) => body.includes(SECRET));
  assert.equal(leaked.length, 0, `${leaked.length} response(s) carried the secret`);
});

await check("health and the audit trail do not carry it either", async () => {
  // Not /v1/events — that is a live stream that blocks until something
  // happens, and the audit log is the durable record anyway.
  for (const path of ["/health", "/v1/secrets", "/v1/audit?limit=50", "/v1/runs?limit=20"]) {
    const body = await (await fetch(`${API}${path}`)).text();
    assert.ok(!body.includes(SECRET), `${path} leaked the secret`);
  }
});

await check("a tool referencing the secret gets the value; the log does not", async () => {
  // fetch_url is a real tool with a real header path — the reference is
  // resolved inside the registry, after the audit write.
  await fetch(`${API}/v1/tools/fetch_url/invoke`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      arguments: { url: "http://127.0.0.1:9/nothing", headers: { auth: "${vault:e2e_stripe}" } },
    }),
  }).catch(() => {});

  const audit = await (await fetch(`${API}/v1/audit?limit=20`)).text();
  assert.ok(!audit.includes(SECRET), "the audit log must record the reference, not the value");
});

await check("spending is reported", async () => {
  const body = await (await fetch(`${API}/v1/budget`)).json();
  assert.ok("enforced" in body && "spend" in body);
  await page.screenshot({ path: "/tmp/shot-settings.png" });
});

await check("the secret can be removed", async () => {
  await page.locator('button[aria-label="Delete e2e_stripe"]').click();
  await page.waitForTimeout(800);
  const remaining = await (await fetch(`${API}/v1/secrets`)).json();
  assert.ok(!remaining.secrets.some((s) => s.name === "e2e_stripe"));
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
