import { app, BrowserWindow, session } from "electron";
import { registerCommandHandlers } from "../ipc/register-command-handlers";
import { createMainWindow, type SunshineWindow } from "../window/create-main-window";

async function bootstrap(): Promise<void> {
  await app.whenReady();
  session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
  let activeWindow: SunshineWindow | undefined = createMainWindow();
  registerCommandHandlers(() => activeWindow?.browser);
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) activeWindow = createMainWindow();
  });
}

void bootstrap();
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
