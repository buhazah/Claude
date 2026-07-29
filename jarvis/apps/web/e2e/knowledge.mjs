/**
 * Knowledge end-to-end: ingest through the UI, retrieve with a citation.
 *
 * The property under test is not "search returns something" — it is that what
 * comes back is *attributable*. A passage without a reference is the failure
 * this whole milestone exists to prevent.
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

await page.goto(`${WEB}/knowledge`, { waitUntil: "networkidle" });
await page.waitForTimeout(1000);

await check("pasted text is ingested from the page", async () => {
  await page
    .locator('input[placeholder*="Paste a URL"]')
    .fill("The Q3 board meeting is on 14 September in Lisbon.");
  await page.getByRole("button", { name: "Ingest" }).click();

  await page.locator("text=/Ingested/").waitFor({ timeout: 10000 });
  const body = await page.locator("main").innerText();
  assert.match(body, /chunks/);
});

await check("the document appears in the library", async () => {
  await page.waitForTimeout(600);
  const body = await page.locator("main").innerText();
  assert.match(body, /Q3 board meeting/);
});

await check("searching returns a passage with its citation", async () => {
  await page.locator('input[placeholder*="Ask across"]').fill("when is the board meeting");
  await page.locator("text=Passages").waitFor({ timeout: 10000 });

  const body = await page.locator("main").innerText();
  assert.match(body, /14 September/, "the passage should be shown");
  assert.match(body, /lex .* sem /, "the retrieval signals should be visible");
  await page.screenshot({ path: "/tmp/shot-knowledge.png" });
});

await check("the API returns an attributable citation", async () => {
  const hits = await (
    await fetch(`${API}/v1/knowledge/search?q=where%20is%20the%20board%20meeting`)
  ).json();

  assert.ok(hits.length > 0, "expected a hit");
  assert.ok(hits[0].reference, "every hit must carry a reference");
  assert.match(hits[0].snippet, /Lisbon/);
  assert.ok(hits[0].signals.lexical >= 0 && hits[0].signals.semantic >= 0);
});

await check("an agent's knowledge tool returns the same citation", async () => {
  const response = await fetch(`${API}/v1/tools/search_documents/invoke`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ arguments: { query: "board meeting location" } }),
  });
  const { result } = await response.json();

  assert.ok(result.length > 0);
  assert.ok(result[0].reference, "the agent must receive the reference with the text");
  // Retrieved content is untrusted by construction, and labelled as such.
  assert.ok("untrusted_content" in result[0]);
});

await check("a document can be forgotten", async () => {
  const documents = await (await fetch(`${API}/v1/knowledge`)).json();
  const removed = await fetch(`${API}/v1/knowledge/${documents[0].id}`, { method: "DELETE" });
  assert.equal(removed.status, 204);

  const hits = await (await fetch(`${API}/v1/knowledge/search?q=board%20meeting`)).json();
  assert.equal(hits.length, 0, "a forgotten document must stop being retrievable");
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
