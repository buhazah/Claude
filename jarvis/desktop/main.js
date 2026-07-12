// JARVIS desktop companion (Electron main process).
// A frameless, always-on-top window that floats your JARVIS over other apps,
// with a global hotkey, a tray icon, and native screen capture exposed to the
// page through preload.js.
const {
  app, BrowserWindow, globalShortcut, ipcMain, desktopCapturer,
  screen, Tray, Menu, nativeImage, shell,
} = require("electron");
const path = require("path");

// Which JARVIS to load. Point at your deployment, or a local dev server.
const JARVIS_URL = process.env.JARVIS_URL || "https://jarvis-56ml.onrender.com";

let win = null;
let tray = null;

// Optional native input control (mouse/keyboard). Only present if the user
// installed it (`npm install`); computer-control features stay disabled without it.
let nut = null;
try { nut = require("@nut-tree-fork/nut-js"); } catch (e) { nut = null; }

function createWindow() {
  const { width } = screen.getPrimaryDisplay().workAreaSize;
  win = new BrowserWindow({
    width: 440,
    height: 680,
    x: Math.max(0, width - 470),
    y: 70,
    frame: false,
    transparent: false,
    resizable: true,
    skipTaskbar: false,
    alwaysOnTop: true,
    backgroundColor: "#17130d",
    title: "JARVIS",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  // Float above full-screen apps too.
  win.setAlwaysOnTop(true, "screen-saver");
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  win.loadURL(JARVIS_URL);

  // Open external links (OAuth popups, etc.) in the user's real browser.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith(JARVIS_URL)) return { action: "allow" };
    shell.openExternal(url);
    return { action: "deny" };
  });

  win.on("closed", () => (win = null));
}

function toggleWindow() {
  if (!win) return createWindow();
  win.isVisible() ? win.hide() : (win.show(), win.focus());
}

function createTray() {
  // A simple gold dot icon drawn in-memory (no asset file needed).
  const size = 16;
  const png = nativeImage.createFromDataURL(
    "data:image/svg+xml;base64," +
      Buffer.from(
        `<svg xmlns='http://www.w3.org/2000/svg' width='${size}' height='${size}'>` +
          `<circle cx='8' cy='8' r='6' fill='none' stroke='#d6af69' stroke-width='1.5'/>` +
          `<circle cx='8' cy='8' r='2.5' fill='#d6af69'/></svg>`
      ).toString("base64")
  );
  tray = new Tray(png.isEmpty() ? nativeImage.createEmpty() : png);
  tray.setToolTip("JARVIS");
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "Show / Hide JARVIS  (Ctrl+Shift+J)", click: toggleWindow },
      { label: "Reload", click: () => win && win.reload() },
      { type: "separator" },
      { label: "Quit", click: () => app.quit() },
    ])
  );
  tray.on("click", toggleWindow);
}

// --- Native bridges called from preload.js -------------------------------
ipcMain.handle("capture-screen", async () => {
  const { width, height } = screen.getPrimaryDisplay().size;
  const sources = await desktopCapturer.getSources({
    types: ["screen"],
    thumbnailSize: { width: Math.min(width, 1600), height: Math.min(height, 1000) },
  });
  if (!sources.length) return null;
  return sources[0].thumbnail.toDataURL();
});
ipcMain.handle("win-minimize", () => win && win.minimize());
ipcMain.handle("win-hide", () => win && win.hide());
ipcMain.handle("win-close", () => app.quit());
ipcMain.handle("win-pin", (_e, on) => win && win.setAlwaysOnTop(!!on, "screen-saver"));

// --- Computer control (mouse/keyboard) — only if nut-js is installed ------
ipcMain.handle("control-available", () => !!nut);

// Full-resolution capture for control (returns size so the model's pixel
// coordinates map 1:1 to the real screen).
ipcMain.handle("capture-display", async () => {
  const { width, height } = screen.getPrimaryDisplay().size;
  const sources = await desktopCapturer.getSources({
    types: ["screen"], thumbnailSize: { width, height },
  });
  if (!sources.length) return null;
  return { dataUrl: sources[0].thumbnail.toDataURL(), width, height };
});

const KEY_MAP = () => {
  const K = nut.Key;
  return {
    Return: K.Enter, Enter: K.Enter, Tab: K.Tab, Escape: K.Escape, Esc: K.Escape,
    space: K.Space, BackSpace: K.Backspace, Delete: K.Delete, Home: K.Home, End: K.End,
    Up: K.Up, Down: K.Down, Left: K.Left, Right: K.Right, Page_Up: K.PageUp, Page_Down: K.PageDown,
    ctrl: K.LeftControl, control: K.LeftControl, alt: K.LeftAlt, shift: K.LeftShift,
    cmd: K.LeftSuper, super: K.LeftSuper, win: K.LeftSuper,
  };
};

async function pressCombo(combo) {
  const map = KEY_MAP();
  const parts = String(combo).split("+").map((s) => s.trim());
  const keys = parts.map((p) => map[p] || (nut.Key[p.toUpperCase()] ?? nut.Key[p]));
  const valid = keys.filter((k) => k !== undefined);
  if (!valid.length) return;
  await nut.keyboard.pressKey(...valid);
  await nut.keyboard.releaseKey(...valid);
}

ipcMain.handle("exec-action", async (_e, a) => {
  if (!nut) return { ok: false, error: "control-not-installed" };
  try {
    const { mouse, keyboard, Button, Point, straightTo } = nut;
    mouse.config.mouseSpeed = 3000;
    keyboard.config.autoDelayMs = 8;
    const at = (c) => new Point(Math.round(c[0]), Math.round(c[1]));
    switch (a.action) {
      case "mouse_move": await mouse.setPosition(at(a.coordinate)); break;
      case "left_click": if (a.coordinate) await mouse.setPosition(at(a.coordinate)); await mouse.leftClick(); break;
      case "right_click": if (a.coordinate) await mouse.setPosition(at(a.coordinate)); await mouse.rightClick(); break;
      case "middle_click": if (a.coordinate) await mouse.setPosition(at(a.coordinate)); await mouse.click(Button.MIDDLE); break;
      case "double_click": if (a.coordinate) await mouse.setPosition(at(a.coordinate)); await mouse.doubleClick(Button.LEFT); break;
      case "left_click_drag":
        await mouse.pressButton(Button.LEFT);
        await mouse.move(straightTo(at(a.coordinate)));
        await mouse.releaseButton(Button.LEFT);
        break;
      case "type": await keyboard.type(a.text || ""); break;
      case "key": await pressCombo(a.text || ""); break;
      case "scroll": {
        const amt = (a.scroll_amount || 3) * 100;
        const d = a.scroll_direction;
        if (a.coordinate) await mouse.setPosition(at(a.coordinate));
        if (d === "up") await mouse.scrollUp(amt);
        else if (d === "down") await mouse.scrollDown(amt);
        else if (d === "left") await mouse.scrollLeft(amt);
        else if (d === "right") await mouse.scrollRight(amt);
        break;
      }
      case "wait": await new Promise((r) => setTimeout(r, Math.min((a.duration || 1) * 1000, 5000))); break;
      case "cursor_position": { const p = await mouse.getPosition(); return { ok: true, x: p.x, y: p.y }; }
      case "screenshot": return { ok: true, screenshot: true };
      default: return { ok: false, error: "unsupported action: " + a.action };
    }
    return { ok: true };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
});

app.whenReady().then(() => {
  createWindow();
  createTray();
  globalShortcut.register("CommandOrControl+Shift+J", toggleWindow);
  // Emergency stop for computer-control — works even when another app has focus.
  globalShortcut.register("CommandOrControl+Shift+Escape", () => {
    if (win) { win.webContents.send("jarvis-stop"); win.show(); win.focus(); }
  });
});

app.on("window-all-closed", () => {
  // Keep running in the tray on macOS; quit elsewhere is handled via tray.
  if (process.platform !== "darwin") { /* stay alive in tray */ }
});
app.on("activate", () => { if (!win) createWindow(); });
app.on("will-quit", () => globalShortcut.unregisterAll());
