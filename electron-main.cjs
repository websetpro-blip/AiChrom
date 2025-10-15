const { app, BrowserWindow, Menu } = require("electron");
const path = require("path");

function startServerInsideElectron() {
  try { 
    require(path.join(__dirname, "dist", "server", "index.js")); 
    console.log("[MAIN] API server started");
  }
  catch (e) { console.error("[MAIN] API start error:", e); }
}
function createWindow() {
  const win = new BrowserWindow({
    width: 1280, height: 820, backgroundColor: "#0f141b", show: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false }
  });
  win.loadFile(path.join(__dirname, "ui", "index.html"));
}
app.whenReady().then(() => { Menu.setApplicationMenu(null); startServerInsideElectron(); createWindow(); });
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });