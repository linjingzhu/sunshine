export const commandIds = ["app.getVersion"] as const;
export type CommandId = (typeof commandIds)[number];

export interface CommandRequest {
  id: CommandId;
}

export type CommandResult =
  | { ok: true; value?: string }
  | { ok: false; error: { code: string; message: string } };

export function isCommandRequest(value: unknown): value is CommandRequest {
  if (!value || typeof value !== "object") return false;
  return commandIds.includes((value as CommandRequest).id);
}
