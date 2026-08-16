import { describe, expect, it } from "vitest";
import { classifyNavigationInput } from "../../src/main/navigation/classify-input";

describe("classifyNavigationInput", () => {
  it("upgrades domains to HTTPS", () => expect(classifyNavigationInput("github.com")).toEqual({ kind: "url", url: "https://github.com" }));
  it("preserves valid HTTPS URLs", () => expect(classifyNavigationInput("https://example.com/path")).toEqual({ kind: "url", url: "https://example.com/path" }));
  it("allows HTTP only for local development", () => {
    expect(classifyNavigationInput("localhost:3000")).toEqual({ kind: "url", url: "http://localhost:3000" });
    expect(classifyNavigationInput("http://example.com").kind).toBe("blocked");
  });
  it("turns plain text into a search", () => expect(classifyNavigationInput("sunshine browser")).toMatchObject({ kind: "search", query: "sunshine browser" }));
  it.each(["javascript:alert(1)", "file:///etc/passwd", "data:text/html,test", ""])("blocks unsafe input %s", (input) => expect(classifyNavigationInput(input).kind).toBe("blocked"));
});
