import { describe, expect, it } from "vitest";
import { checkFile, MAX_UPLOAD_BYTES, passwordStrongEnough } from "./validation";

describe("checkFile", () => {
  it("accepts supported images under the limit", () => {
    expect(checkFile({ type: "image/jpeg", size: 1000 })).toBeNull();
    expect(checkFile({ type: "image/png", size: MAX_UPLOAD_BYTES })).toBeNull();
    expect(checkFile({ type: "image/webp", size: 10 })).toBeNull();
  });
  it("rejects unsupported types before size", () => {
    expect(checkFile({ type: "image/gif", size: 10 })).toBe("badType");
    expect(checkFile({ type: "application/pdf", size: MAX_UPLOAD_BYTES * 2 })).toBe("badType");
  });
  it("rejects files over 4 MB", () => {
    expect(checkFile({ type: "image/jpeg", size: MAX_UPLOAD_BYTES + 1 })).toBe("tooLarge");
  });
});

describe("passwordStrongEnough", () => {
  it.each([["abc12345", true], ["abcdefgh", false], ["12345678", false], ["a1", false], ["Pässwört9", true]])("%s -> %s", (pw, ok) => {
    expect(passwordStrongEnough(pw)).toBe(ok);
  });
});
