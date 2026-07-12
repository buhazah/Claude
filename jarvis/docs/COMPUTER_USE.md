# Computer Control (Computer Use)

Let JARVIS **drive your mouse and keyboard** to do things on your computer —
open apps, fill forms, click around — using Anthropic's computer-use capability.
This is the most powerful feature in JARVIS, so it is **off by default,
owner-only, supervised, and stoppable at any moment.**

> ⚠️ **Read this first.** When enabled and running, JARVIS can move your mouse,
> type, and click **anywhere on your screen** — like a person using your
> computer. Only run it while you're watching. Never leave it unattended.
> Emergency stop is **Ctrl/Cmd + Shift + Esc** at any time.

## How it works (and why it's safe by design)

```
Desktop app (your PC)                         JARVIS server (holds API key)
  capture screen ─────────────────────────►  /api/computer/step
        ▲                                        │  asks Claude for ONE next action
        │ execute action locally (nut-js)        ▼
  ◄──────────────────────────────────────── returns the action
  screenshot the result, loop…
```

- The **server never touches your input** — it only tells the desktop app the
  *next* action to take. Your mouse/keyboard are driven **locally** on your PC.
- Your **API key stays on the server**, never on your desktop.
- Every run is: **owner-only** + **globally gated** + (by default)
  **confirm-each-action** + **step-capped** + **STOP any time**.

## Turn it on

Three things must all be true:

1. **Enable it on the server.** Set `JARVIS_ENABLE_COMPUTER_USE=true`
   (Render → your service → Environment), then redeploy. Optional tuning:
   - `JARVIS_COMPUTER_MODEL` (default `claude-haiku-4-5-20251001` — the model
     verified to support the computer tool on this account)
   - `JARVIS_COMPUTER_MAX_STEPS` (default `30`)
2. **Install input support in the desktop app.** The native mouse/keyboard
   module is an *optional* dependency:
   ```bash
   cd jarvis/desktop
   npm install        # pulls in @nut-tree-fork/nut-js (prebuilt binaries)
   npm start
   ```
   If it isn't installed, the 🖱️ button explains what's missing — everything
   else in the desktop app still works.
3. **Be the owner account.** Only the first (owner) user can control the
   computer.

## Using it

1. In the desktop app, click the **🖱️ button** (bottom-right).
2. Type what you want, e.g. *"open Notepad and type my email signature."*
3. Keep **"Ask me before each action"** checked (default) the first few times —
   you approve each click/keystroke.
4. Watch the live action log. Hit **STOP** (or **Ctrl/Cmd+Shift+Esc**) anytime.

## Safety controls (all on by default)

| Control | What it does |
|--------|--------------|
| Global gate | `JARVIS_ENABLE_COMPUTER_USE` must be `true`; otherwise every request is 403 |
| Owner-only | Members/viewers can never drive the computer |
| Supervised mode | Confirms **each** action before it runs |
| Emergency stop | `Ctrl/Cmd+Shift+Esc` (global) or the STOP button |
| Step cap | Stops after `JARVIS_COMPUTER_MAX_STEPS` actions |
| System prompt guardrail | Claude is told never to take destructive/irreversible actions (delete, send, purchase, security changes) without explicit instruction |
| Local execution | Input happens on your PC only; the server can't act on its own |

## Limits & notes

- **Windows display scaling / multi-monitor:** coordinates are mapped from the
  primary display at its reported size. On high-DPI setups (e.g. 150% scaling)
  or multiple monitors, clicks can be slightly off; set your primary display to
  100% scaling for best accuracy, or tune the capture size in `main.js`.
- It controls the **primary display** only.
- Best for simple, visible GUI tasks. It is not a substitute for real APIs —
  for email/calendar, the Gmail/Calendar **integrations** are more reliable.
- Turn `JARVIS_ENABLE_COMPUTER_USE` back to `false` when you're done to keep the
  capability dormant.
