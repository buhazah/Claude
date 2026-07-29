/**
 * Launching Chromium, wherever it happens to live.
 *
 * The dev container ships a browser at a known path; a CI runner has whatever
 * `playwright install` put in its cache. Eight suites each hardcoding the
 * first of those meant they could only ever run in one of the two places —
 * which is why the e2e suites, the checks that have caught the most real bugs
 * in this project, were never wired into CI.
 *
 * `executablePath` is passed only when a browser is actually there. Otherwise
 * Playwright resolves its own, which is the case CI wants.
 */

import { existsSync } from "node:fs";
import { chromium } from "playwright";

const PREINSTALLED = process.env.CHROMIUM_PATH ?? "/opt/pw-browsers/chromium";

export async function launchBrowser(options = {}) {
  const executablePath = existsSync(PREINSTALLED) ? PREINSTALLED : undefined;
  return chromium.launch({ ...options, ...(executablePath ? { executablePath } : {}) });
}

/**
 * Wait for an HTTP endpoint to answer. CI starts servers in the background,
 * and a suite that races them fails in a way that looks like a product bug.
 */
export async function waitForServer(url, { timeoutMs = 90_000, label = url } = {}) {
  const deadline = Date.now() + timeoutMs;
  let lastError = "no attempt made";
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
      lastError = `HTTP ${response.status}`;
    } catch (error) {
      lastError = String(error.cause?.code ?? error.message);
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`${label} never became ready within ${timeoutMs}ms — last: ${lastError}`);
}
