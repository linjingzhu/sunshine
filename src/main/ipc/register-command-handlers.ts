import { app, ipcMain, type IpcMainInvokeEvent } from "electron";
import type { BrowserSurface } from "../browser/browser-surface";
import { isCommandRequest, type CommandResult } from "../../shared/commands/command";
import { ipcChannels } from "../../shared/contracts/channels";

export function registerCommandHandlers(getBrowser: () => BrowserSurface | undefined): void {
  ipcMain.removeHandler(ipcChannels.executeCommand);
  ipcMain.handle(ipcChannels.executeCommand, async (event, request: unknown): Promise<CommandResult> => {
    if (!isTrustedRenderer(event)) return failure("UNTRUSTED_SENDER", "신뢰할 수 없는 화면의 요청입니다.");
    if (!isCommandRequest(request)) return failure("INVALID_COMMAND", "지원하지 않는 명령입니다.");
    if (request.id === "app.getVersion") return { ok: true, value: app.getVersion() };

    const browser = getBrowser();
    if (!browser) return failure("BROWSER_UNAVAILABLE", "브라우저 창을 사용할 수 없습니다.");
    try {
      switch (request.id) {
        case "browser.getState": return { ok: true, browser: browser.snapshot() };
        case "browser.navigate": return { ok: true, browser: await browser.navigate(request.input) };
        case "browser.back": return { ok: true, browser: browser.back() };
        case "browser.forward": return { ok: true, browser: browser.forward() };
        case "browser.reload": return { ok: true, browser: browser.reload() };
        case "browser.stop": return { ok: true, browser: browser.stop() };
      }
    } catch {
      return failure("COMMAND_FAILED", "브라우저 명령을 완료하지 못했습니다.");
    }
  });
}

function isTrustedRenderer(event: IpcMainInvokeEvent): boolean {
  try {
    if (!event.senderFrame) return false;
    const sender = new URL(event.senderFrame.url);
    const devServerUrl = process.env.VITE_DEV_SERVER_URL;
    if (devServerUrl) return sender.origin === new URL(devServerUrl).origin;
    return sender.protocol === "file:";
  } catch {
    return false;
  }
}

function failure(code: string, message: string): CommandResult {
  return { ok: false, error: { code, message } };
}
