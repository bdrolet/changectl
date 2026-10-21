import { describe, expect, it, vi } from "vitest";

vi.mock("@/auth", () => ({ auth: vi.fn() }));
vi.mock("next/headers", () => ({ headers: vi.fn() }));
vi.mock("next-auth/jwt", () => ({ getToken: vi.fn() }));

import { CODES, describe as describeCode, describeError } from "@/lib/errors";

describe("describe", () => {
  it("maps every code to a plain sentence", () => {
    for (const code of CODES) {
      const text = describeCode(code);
      expect(text, code).not.toBe("");
      expect(text, code).not.toBe(code);
      expect(text, code).not.toBe("Something went wrong.");
    }
  });

  it("falls back for unknown codes", () => {
    expect(describeCode("nope")).toBe("Something went wrong.");
  });

  it("appends the offending changes", async () => {
    const { ApiError } = await import("@/lib/api");
    const e = new ApiError(409, "pending_approver", "x", ["CHG-1", "CHG-2"]);
    expect(describeError(e)).toBe(
      `${describeCode("pending_approver")}: CHG-1, CHG-2`,
    );
    expect(describeError(new Error("x"))).toBe("Something went wrong.");
  });
});
