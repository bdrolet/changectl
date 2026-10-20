import { describe, expect, it } from "vitest";

import { bytes, dateOnly, relativeAge } from "@/lib/format";

const NOW = Date.parse("2026-06-10T12:00:00Z");
const ago = (s: number) => new Date(NOW - s * 1000).toISOString();

describe("relativeAge", () => {
  it("is just now under a minute", () => {
    expect(relativeAge(ago(59), NOW)).toBe("just now");
  });
  it("floors minutes, hours, days, weeks", () => {
    expect(relativeAge(ago(90), NOW)).toBe("1m");
    expect(relativeAge(ago(2 * 3600 + 60), NOW)).toBe("2h");
    expect(relativeAge(ago(3 * 86400), NOW)).toBe("3d");
    expect(relativeAge(ago(15 * 86400), NOW)).toBe("2w");
  });
});

describe("bytes", () => {
  it("formats B, KB, MB", () => {
    expect(bytes(512)).toBe("512 B");
    expect(bytes(2048)).toBe("2.0 KB");
    expect(bytes(1258291)).toBe("1.2 MB");
  });
});

describe("dateOnly", () => {
  it("is the UTC date", () => {
    expect(dateOnly("2026-06-08T23:58:52Z")).toBe("2026-06-08");
  });
});
