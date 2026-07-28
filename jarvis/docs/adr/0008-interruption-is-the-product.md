# ADR 0008 — Interruption is the product, and it truncates history

**Status:** accepted · M7

## Context

Voice assistants are judged on one thing: what happens when you talk over them.
Everything else — recognition accuracy, voice quality, latency — is table
stakes that vendors supply. Barge-in is the part the application owns, and it
is where the design decisions are.

Two bugs define the space, and both are easy to ship:

1. **Stopping the audio but not the model.** The assistant goes quiet, so it
   looks interrupted, while generation runs to completion in the background —
   burning tokens on words nobody will hear, and finishing after the user has
   already asked something else. The next turn then contends with a completed
   response the user never heard.
2. **Remembering what was generated rather than what was heard.** The user
   interrupts three words in, and the transcript records the full paragraph.
   From then on the model reasons about a conversation that did not happen, and
   will happily refer back to advice it never actually gave.

## Decision

**An interruption cancels the whole turn, and the turn is recorded as truncated.**

* `interrupt()` cancels one `asyncio.Task` that owns *both* generation and
  playback. There is no path that stops one without the other; they are the
  same task by construction, not by discipline.
* `Turn` carries `generated` and `spoken` separately. `spoken` is appended
  **per audio frame, as the frame finishes playing** — not per sentence and not
  when synthesis is requested. If the user cuts in halfway through a sentence,
  the turn records the half they heard.
* Replayed history uses `spoken`, and appends `[interrupted here]` when
  `truncated`. Telling the model it was cut off is cheaper and more honest than
  letting it infer that from a sentence ending mid-word.
* **A partial transcript triggers barge-in; only a final transcript is
  answered.** Waiting for a final transcript before ducking is the delay that
  makes an assistant feel like it is talking over you. The two signals do
  different jobs and are handled separately in `hear()`.

Supporting decisions:

* **Recognition happens in the browser by default.** No audio leaves the
  machine unless a speech key is configured, and the interrupt fires locally
  without a server round trip. A hosted transcriber exists behind the same port
  for browsers that lack one.
* **Sentence-level synthesis.** The segmenter releases a unit as soon as it is
  a complete thought, so speaking starts while the model is still generating.
  It refuses to split on abbreviations and decimals, because a fragment spoken
  aloud cannot be un-said.
* **Wake-word matching is deliberately tight** — one edit, at the start of the
  utterance only. `Jervis`/`Harvis`/`Arvis` wake it; `Travis` (three edits) and
  `Charvis` (two) do not, and "I was telling Jarvis about it" is a mention, not
  a summons. Loosening the threshold to catch phonetic near-misses trades false
  negatives for false positives, and a false positive means the assistant
  starts listening to a conversation it was not invited to. Real phonetic
  matching belongs in a device-side acoustic model, not in string distance.

## Consequences

- **The offline speaker must be paced in production.** This was a real bug
  found by the browser test, not a hypothetical: an unpaced speaker finishes a
  turn in ~30 ms, so nobody — user or test — can ever interrupt. Pacing is now
  a setting (`realtime_speech`), on by default and off in the unit suite. An
  instantaneous speaker makes every barge-in test pass vacuously.
- Cost accounting is honest about cancelled turns: they consumed the tokens
  generated before the cancel, and no more.
- The session holds conversation state in memory. A dropped socket loses the
  conversation, which is correct for voice — nobody resumes a spoken turn from
  yesterday — but it means voice history is not a memory substitute. Anything
  worth keeping goes through the normal memory writes the agent already makes.
- Barge-in is verified end-to-end through a real browser against a real kernel,
  with only the `SpeechRecognition` API stubbed. The assertion is the one that
  matters: after an interruption the surviving reply is a strict *prefix* of
  what was generated.
