import { BrowserWindow } from "electron";
import path from "node:path";
import { BrowserSurface } from "../browser/browser-surface";

export interface SunshineWindow { window: BrowserWindow; browser: BrowserSurface }

export function createMainWindow(): SunshineWindow {
  const window = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 760,
    minHeight: 560,
    backgroundColor: "#f7f7f3",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "../../preload/sunshine-api.js"),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
    },
  });

  window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  window.webContents.on("will-navigate", (event, url) => {
    const allowed = process.env.VITE_DEV_SERVER_URL
      ? url.startsWith(process.env.VITE_DEV_SERVER_URL)
      : url.startsWith("file:");
    if (!allowed) event.preventDefault();
  });
  window.once("ready-to-show", () => window.show());

  const devServerUrl = process.env.VITE_DEV_SERVER_URL;
  if (devServerUrl) void window.loadURL(devServerUrl);
  else void window.loadFile(path.join(__dirname, "../../renderer/index.html"));
  const browser = new BrowserSurface(window);
  void browser.start();
  return { window, browser };
}
