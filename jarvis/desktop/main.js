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

app.whenReady().then(() => {
  createWindow();
  createTray();
  globalShortcut.register("CommandOrControl+Shift+J", toggleWindow);
});

app.on("window-all-closed", () => {
  // Keep running in the tray on macOS; quit elsewhere is handled via tray.
  if (process.platform !== "darwin") { /* stay alive in tray */ }
});
app.on("activate", () => { if (!win) createWindow(); });
app.on("will-quit", () => globalShortcut.unregisterAll());
