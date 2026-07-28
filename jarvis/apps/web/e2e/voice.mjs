/**
 * End-to-end voice, through a real browser against a real kernel.
 *
 * Headless Chromium has no speech recogniser and no microphone, so the browser
 * API is stubbed — but nothing below it is. The component, the WebSocket, the
 * session state machine, the segmenter and the speaker are all the real ones,
 * which is where every interesting bug in voice actually lives.
 *
 * The check that matters is barge-in: when the user talks over Jarvis, the
 * reply on screen must collapse to what was *spoken* before the interruption,
 * not what the model had already generated.
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

// A recogniser that says exactly what the test tells it to. Installed before
// any app code runs so the component picks it up on mount.
await page.addInitScript(() => {
  class FakeRecognition {
    constructor() {
      this.onresult = null;
      this.onerror = null;
      this.onend = null;
      window.__speech = this;
    }
    start() {}
    stop() {}
    abort() {}
  }
  window.SpeechRecognition = FakeRecognition;
  window.__hear = (transcript, isFinal) => {
    const results = [{ 0: { transcript }, isFinal, length: 1 }];
    results.length = 1;
    window.__speech.onresult({ resultIndex: 0, results });
  };
});

/**
 * Collect kernel events matching `topics` in the background. Returns a getter
 * for what has arrived so far — used to prove the interruption reached the bus,
 * not just the screen.
 */
function watchEvents(topics) {
  const seen = [];
  const controller = new AbortController();
  const done = (async () => {
    const response = await fetch(`${API}/v1/events?topics=${encodeURIComponent(topics)}`, {
      signal: controller.signal,
    });
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      for (const line of decoder.decode(value).split("\n")) {
        if (line.startsWith("event: ")) seen.push(line.slice(7).trim());
      }
    }
  })().catch(() => {});
  return { seen, stop: () => (controller.abort(), done) };
}

const status = async () =>
  (await page.locator('[role="dialog"] p').first().innerText()).toLowerCase();
const reply = () => page.getByTestId("voice-reply").innerText().catch(() => "");

/** Wait until the overlay reports one of `wanted`, or throw with what it said. */
const waitForStatus = async (wanted, timeout = 20000) => {
  const deadline = Date.now() + timeout;
  let seen = "";
  while (Date.now() < deadline) {
    seen = await status();
    if (wanted.some((w) => seen.includes(w.toLowerCase()))) return seen;
    await page.waitForTimeout(80);
  }
  throw new Error(`status never reached ${wanted.join("/")} — stuck at "${seen}"`);
};

await page.goto(WEB, { waitUntil: "networkidle" });
await page.waitForTimeout(800);

await check("⌘⇧V opens voice mode", async () => {
  await page.keyboard.press("Control+Shift+V");
  await page.locator('[role="dialog"][aria-label="Voice mode"]').waitFor({ timeout: 5000 });
  assert.match(await status(), /ready|listening/);
  await page.screenshot({ path: "/tmp/shot-voice.png" });
});

await check("speech is transcribed, answered, and spoken", async () => {
  await page.evaluate(() => window.__hear("what is on my plate today", true));

  await waitForStatus(["Thinking", "Speaking"]);
  await waitForStatus(["Speaking"]);

  const shown = await page.locator('[role="dialog"]').innerText();
  assert.match(shown, /what is on my plate today/, "the overlay must show what it heard");
  assert.match(await reply(), /\[echo:/, "the reply must stream in");
});

const voiceEvents = watchEvents("voice.**");

await check("talking over Jarvis truncates the turn to what was heard", async () => {
  // A long utterance, so the echoed reply takes many seconds to speak and
  // generation is comfortably ahead of playback when the interruption lands.
  const long =
    "give me a detailed briefing on the quarter covering revenue pipeline " +
    "hiring runway and the three biggest risks facing the business right now";
  await page.evaluate((text) => window.__hear(text, true), long);
  await waitForStatus(["Speaking"]);
  // Speech is paced at ~14 chars/second in 40-char frames, and a frame counts
  // as heard only once it has finished playing. Let one land, so there is a
  // spoken prefix to compare against — and so the reply is not yet complete.
  await page.waitForTimeout(4000);

  const generated = await reply();
  assert.ok(generated.length > 80, `expected a long reply, got ${generated.length} chars`);

  // A *partial* — the user has started talking but has not finished. This is
  // the real barge-in trigger; waiting for a final transcript is too late.
  await page.evaluate(() => window.__hear("actually wait", false));

  await waitForStatus(["Listening", "Ready"], 8000);
  const kept = await reply();

  assert.ok(kept.length > 0, "the interrupted turn must keep what was spoken");
  assert.ok(
    kept.length < generated.length,
    `interrupted reply (${kept.length}) should be shorter than what was generated (${generated.length})`,
  );
  assert.ok(generated.startsWith(kept), "what was kept must be a prefix of what was generated");
});

await check("the kernel recorded the interruption", async () => {
  await voiceEvents.stop();
  assert.ok(
    voiceEvents.seen.includes("voice.interrupted"),
    `the bus should carry voice.interrupted; saw ${JSON.stringify(voiceEvents.seen)}`,
  );
});

await check("typing reaches the same session", async () => {
  await page.getByTestId("voice-input").fill("hello by hand");
  await page.keyboard.press("Enter");
  await waitForStatus(["Thinking", "Speaking"]);
  assert.match(await page.locator('[role="dialog"]').innerText(), /hello by hand/);
});

await check("closing voice mode tears the session down", async () => {
  await page.keyboard.press("Escape");
  await page.waitForTimeout(600);
  assert.equal(await page.locator('[role="dialog"][aria-label="Voice mode"]').count(), 0);
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
