// Preload bridge: safely exposes native desktop powers to the JARVIS web page,
// and injects a slim draggable title bar (since the window is frameless).
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("jarvisDesktop", {
  isDesktop: true,
  captureScreen: () => ipcRenderer.invoke("capture-screen"),
  minimize: () => ipcRenderer.invoke("win-minimize"),
  hide: () => ipcRenderer.invoke("win-hide"),
  close: () => ipcRenderer.invoke("win-close"),
  setPinned: (on) => ipcRenderer.invoke("win-pin", on),
  // Computer control (only functional if @nut-tree-fork/nut-js is installed).
  controlAvailable: () => ipcRenderer.invoke("control-available"),
  captureDisplay: () => ipcRenderer.invoke("capture-display"),
  execAction: (action) => ipcRenderer.invoke("exec-action", action),
  onStop: (cb) => ipcRenderer.on("jarvis-stop", () => cb()),
});

// Inject a draggable top strip + window buttons into whatever page loads.
window.addEventListener("DOMContentLoaded", () => {
  const bar = document.createElement("div");
  bar.id = "jarvis-desktop-bar";
  bar.innerHTML =
    '<span class="jd-title">JARVIS</span>' +
    '<span class="jd-spacer"></span>' +
    '<button class="jd-btn" id="jd-min" title="Minimize">—</button>' +
    '<button class="jd-btn" id="jd-hide" title="Hide (Ctrl+Shift+J)">▾</button>' +
    '<button class="jd-btn jd-close" id="jd-close" title="Quit">✕</button>';
  const style = document.createElement("style");
  style.textContent = `
    #jarvis-desktop-bar{position:fixed;top:0;left:0;right:0;height:30px;z-index:99999;
      display:flex;align-items:center;gap:2px;padding:0 6px 0 12px;
      background:rgba(20,16,11,0.92);border-bottom:1px solid #3a2f1e;
      -webkit-app-region:drag;user-select:none;font-family:system-ui,sans-serif}
    #jarvis-desktop-bar .jd-title{font-size:12px;letter-spacing:3px;color:#d6af69;font-weight:600}
    #jarvis-desktop-bar .jd-spacer{flex:1}
    #jarvis-desktop-bar .jd-btn{-webkit-app-region:no-drag;width:28px;height:22px;
      border-radius:5px;background:transparent;color:#a99a78;font-size:13px;cursor:pointer;border:none}
    #jarvis-desktop-bar .jd-btn:hover{background:rgba(214,175,105,0.15);color:#eee4d2}
    #jarvis-desktop-bar .jd-close:hover{background:#a33;color:#fff}
    body{padding-top:30px !important}`;
  document.head.appendChild(style);
  document.body.appendChild(bar);
  document.getElementById("jd-min").onclick = () => window.jarvisDesktop.minimize();
  document.getElementById("jd-hide").onclick = () => window.jarvisDesktop.hide();
  document.getElementById("jd-close").onclick = () => window.jarvisDesktop.close();
});
