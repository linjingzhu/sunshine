import { describe, expect, it } from "vitest";
import { isCommandRequest } from "../../src/shared/commands/command";

describe("isCommandRequest", () => {
  it("accepts an allow-listed command", () => expect(isCommandRequest({ id: "app.getVersion" })).toBe(true));
  it("requires input for navigation", () => {
    expect(isCommandRequest({ id: "browser.navigate", input: "github.com" })).toBe(true);
    expect(isCommandRequest({ id: "browser.navigate" })).toBe(false);
  });
  it("rejects unknown or malformed commands", () => {
    expect(isCommandRequest({ id: "filesystem.read" })).toBe(false);
    expect(isCommandRequest(null)).toBe(false);
  });
});
