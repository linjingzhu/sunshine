import { contextBridge, ipcRenderer } from "electron";
import { ipcChannels } from "../shared/contracts/channels";
import type { BrowserSnapshot, CommandRequest, CommandResult } from "../shared/commands/command";

export interface SunshineApi {
  executeCommand(request: CommandRequest): Promise<CommandResult>;
  onBrowserStateChanged(listener: (snapshot: BrowserSnapshot) => void): () => void;
}

const api: SunshineApi = {
  executeCommand: (request) => ipcRenderer.invoke(ipcChannels.executeCommand, request),
  onBrowserStateChanged: (listener) => {
    const handler = (_event: Electron.IpcRendererEvent, snapshot: BrowserSnapshot) => listener(snapshot);
    ipcRenderer.on(ipcChannels.browserStateChanged, handler);
    return () => ipcRenderer.removeListener(ipcChannels.browserStateChanged, handler);
  },
};

contextBridge.exposeInMainWorld("sunshine", Object.freeze(api));
