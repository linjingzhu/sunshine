import { app, ipcMain } from "electron";
import { ipcChannels } from "../../shared/contracts/channels";
import { isCommandRequest, type CommandResult } from "../../shared/commands/command";

function isTrustedSender(url: string): boolean {
  const devUrl = process.env.VITE_DEV_SERVER_URL;
  if (devUrl && url.startsWith(devUrl)) return true;
  return url.startsWith("file:");
}

export function registerCommandHandlers(): void {
  ipcMain.handle(ipcChannels.executeCommand, (event, payload: unknown): CommandResult => {
    if (!isTrustedSender(event.senderFrame.url)) {
      return { ok: false, error: { code: "UNTRUSTED_SENDER", message: "요청이 허용되지 않았습니다." } };
    }
    if (!isCommandRequest(payload)) {
      return { ok: false, error: { code: "INVALID_COMMAND", message: "잘못된 명령입니다." } };
    }
    switch (payload.id) {
      case "app.getVersion":
        return { ok: true, value: app.getVersion() };
    }
  });
}
