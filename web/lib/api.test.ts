import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/auth", () => ({
  auth: vi.fn(async () => ({ user: { id: "u1" } })),
}));
vi.mock("next/headers", () => ({ headers: vi.fn(async () => new Headers()) }));
vi.mock("next-auth/jwt", () => ({
  getToken: vi.fn(async () => ({ id_token: "t" })),
}));

import { getToken } from "next-auth/jwt";

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

  it("returns the raw 302 without following it", async () => {
    const fetchMock = vi.fn(
      async (...[,]: unknown[]) =>
        new Response(null, { status: 302, headers: { location: "/x" } }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const res = await apiFetch<Response>("/dl", { raw: true });
    expect(res).toBeInstanceOf(Response);
    expect(res.status).toBe(302);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ redirect: "manual" });
  });

  it("refreshes an expired token in memory for this call", async () => {
    vi.mocked(getToken).mockResolvedValueOnce({
      id_token: "stale",
      refresh_token: "r",
      expires_at: 1,
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id_token: "fresh", expires_in: 3600 })),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true })));
    vi.stubGlobal("fetch", fetchMock);
    await expect(apiFetch("/me")).resolves.toEqual({ ok: true });
    expect(fetchMock.mock.calls[0][0]).toContain("oauth2.googleapis.com");
    const sent = fetchMock.mock.calls[1][1].headers as Headers;
    expect(sent.get("Authorization")).toBe("Bearer fresh");
  });

  it("throws invalid_token when the refresh fails", async () => {
    vi.mocked(getToken).mockResolvedValueOnce({
      id_token: "stale",
      refresh_token: "r",
      expires_at: 1,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 400 })),
    );
    await expect(apiFetch("/me")).rejects.toMatchObject({
      status: 401,
      detail: "invalid_token",
    });
  });
});
