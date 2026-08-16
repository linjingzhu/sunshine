import { contextBridge, ipcRenderer } from "electron";
import { ipcChannels } from "../shared/contracts/channels";
import type { CommandRequest, CommandResult } from "../shared/commands/command";

export interface SunshineApi {
  executeCommand(request: CommandRequest): Promise<CommandResult>;
}

const api: SunshineApi = {
  executeCommand: (request) => ipcRenderer.invoke(ipcChannels.executeCommand, request),
};

contextBridge.exposeInMainWorld("sunshine", Object.freeze(api));
