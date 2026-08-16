import { describe, expect, it } from "vitest";
import { isCommandRequest } from "../../src/shared/commands/command";

describe("isCommandRequest", () => {
  it("accepts an allow-listed command", () => expect(isCommandRequest({ id: "app.getVersion" })).toBe(true));
  it("rejects unknown or malformed commands", () => {
    expect(isCommandRequest({ id: "filesystem.read" })).toBe(false);
    expect(isCommandRequest(null)).toBe(false);
  });
});
