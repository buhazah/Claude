# JARVIS Desktop App

A native desktop companion (Electron) that floats JARVIS **on top of your other
apps** and lets it **see your screen**. It wraps the same JARVIS you already run
— it just gives it a body on your desktop.

## What it adds over the web app
- **Always-on-top floating window** — JARVIS hovers over any app, on any
  workspace, even full-screen apps.
- **Global hotkey** — `Ctrl/Cmd + Shift + J` shows/hides it instantly.
- **Tray icon** — quick show/hide/reload/quit.
- **Screen vision** — the 👁 button captures your screen and JARVIS tells you
  what it sees / gives feedback (via `/api/vision/analyze`). In the desktop app
  this is instant and silent; in a plain browser the same button works via the
  screen-share picker.
- **Frameless, draggable** — a slim gold title bar with minimize/hide/quit.

## Run it (development)
Requires **Node.js 18+**.

```bash
cd jarvis/desktop
npm install
# Point it at your deployment (or a local server):
#   Windows PowerShell:  $env:JARVIS_URL="https://jarvis-56ml.onrender.com"
#   macOS/Linux:         export JARVIS_URL="https://jarvis-56ml.onrender.com"
npm start
```

It opens a floating JARVIS window. Log in as usual. The 👁 button appears
bottom-right.

`JARVIS_URL` defaults to the hosted URL in `main.js`; change it there or via the
env var to target a different instance (e.g. `http://localhost:8700`).

## Build a Windows installer
```bash
cd jarvis/desktop
npm install
npm run build      # produces a one-click .exe in desktop/dist/
```
(Build on the target OS — build the Windows installer on Windows, etc.
`electron-builder` also supports `--mac` and `--linux`.)

## How screen vision works (privacy)
- The screenshot is captured **locally** by Electron (`desktopCapturer`) — or by
  the browser's screen-share in web mode — and sent **once** to your JARVIS
  backend, which forwards it to the configured vision model (Claude or OpenAI)
  and returns the text. Nothing is stored.
- It only fires when **you** click 👁.
- Server needs `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) — the same key already
  powering chat.

## Architecture
```
Electron main (main.js)
  ├─ frameless always-on-top BrowserWindow  → loads your JARVIS URL
  ├─ globalShortcut  Ctrl/Cmd+Shift+J
  ├─ Tray menu
  └─ ipcMain "capture-screen" → desktopCapturer → data URL
        ▲
        │ contextBridge (preload.js) exposes window.jarvisDesktop
        ▼
JARVIS web page (unchanged)
  └─ 👁 button → captureScreen() → POST /api/vision/analyze → shows + speaks
```

## Not included yet
Mouse/keyboard control ("computer use") is a separate, more security-sensitive
phase. The desktop foundation here is what it would build on.
