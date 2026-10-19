import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/auth", () => ({
  auth: vi.fn(async () => ({ user: { id: "u1" } })),
}));
vi.mock("next/headers", () => ({ headers: vi.fn(async () => new Headers()) }));
vi.mock("next-auth/jwt", () => ({
  getToken: vi.fn(async () => ({ id_token: "t" })),
}));

import { apiFetch } from "@/lib/api";

describe("apiFetch", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("maps 403 body to ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "not_invited", message: "x" }), {
            status: 403,
          }),
      ),
    );
    await expect(apiFetch("/me")).rejects.toMatchObject({
      status: 403,
      detail: "not_invited",
    });
  });
});
