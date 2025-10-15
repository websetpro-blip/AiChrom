import { app, BrowserWindow, nativeTheme } from "electron";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const isDev = !app.isPackaged;

function createWindow() {
  nativeTheme.themeSource = "dark";

  const win = new BrowserWindow({
    width: 1280,
    height: 820,
    title: "AiChrome",
    icon: path.join(__dirname, "assets", "icon.ico"),
    backgroundColor: "#0b0f19",
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  if (isDev) {
    win.loadURL("http://localhost:5173");
    win.webContents.openDevTools();
  } else {
    win.loadFile(path.join(__dirname, "dist", "index.html"));
  }
}

app.whenReady().then(createWindow);
app.on("window-all-closed", () => { 
  if (process.platform !== "darwin") app.quit(); 
});
app.on("activate", () => { 
  if (BrowserWindow.getAllWindows().length === 0) createWindow(); 
});
