import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/auth", () => ({ auth: vi.fn() }));
vi.mock("next/headers", () => ({ headers: vi.fn() }));
vi.mock("next-auth/jwt", () => ({ getToken: vi.fn() }));
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("next/navigation", () => ({ redirect: vi.fn() }));
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  apiFetch: vi.fn(),
}));

import { revalidatePath } from "next/cache";

import { ApiError, apiFetch } from "@/lib/api";
import { describe as describeCode } from "@/lib/errors";

import { attachRevision, releaseChange } from "./actions";

function form(): FormData {
  const f = new FormData();
  f.set("file", new File(["x"], "a.pdf", { type: "application/pdf" }));
  f.set("title", "Spec");
  return f;
}

describe("attachRevision", () => {
  beforeEach(() => vi.clearAllMocks());

  it("maps an ApiError to a described result", async () => {
    vi.mocked(apiFetch).mockRejectedValueOnce(
      new ApiError(415, "invalid_file", "bad"),
    );
    expect(await attachRevision("c1", form())).toEqual({
      ok: false,
      error: describeCode("invalid_file"),
    });
    expect(revalidatePath).not.toHaveBeenCalled();
  });

  it("returns ok and revalidates on success", async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce({});
    expect(await attachRevision("c1", form())).toEqual({ ok: true });
    expect(revalidatePath).toHaveBeenCalledWith("/changes");
    expect(revalidatePath).toHaveBeenCalledWith("/changes/c1");
  });

  it("rethrows non-API errors", async () => {
    vi.mocked(apiFetch).mockRejectedValueOnce(new Error("boom"));
    await expect(attachRevision("c1", form())).rejects.toThrow("boom");
  });
});

describe("releaseChange", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns ok and revalidates on success", async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce({});
    expect(await releaseChange("c1", "2026-11-01")).toEqual({ ok: true });
    expect(apiFetch).toHaveBeenCalledWith(
      "/changes/c1/release",
      expect.objectContaining({ body: JSON.stringify({ cutin_date: "2026-11-01" }) }),
    );
    expect(revalidatePath).toHaveBeenCalledWith("/documents");
  });

  it("describes cutin_required", async () => {
    vi.mocked(apiFetch).mockRejectedValueOnce(
      new ApiError(422, "cutin_required", "x"),
    );
    expect(await releaseChange("c1", "")).toEqual({
      ok: false,
      error: describeCode("cutin_required"),
    });
  });
});
