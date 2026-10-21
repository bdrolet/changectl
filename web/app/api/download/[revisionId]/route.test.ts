import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status: number;
    constructor(status: number) {
      super("x");
      this.status = status;
    }
  }
  return { ApiError, apiFetch: vi.fn() };
});

import { apiFetch } from "@/lib/api";

import { GET } from "./route";

const call = (url = "http://app.test/api/download/r1") =>
  GET(new Request(url), {
    params: Promise.resolve({ revisionId: "r1" }),
  } as never);

describe("download relay", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("redirects to /signin on an API 401", async () => {
    vi.mocked(apiFetch).mockResolvedValue(new Response(null, { status: 401 }));
    const res = await call();
    expect(res.status).toBe(302);
    expect(res.headers.get("location")).toBe("http://app.test/signin");
  });

  it("relays a 302 Location", async () => {
    vi.mocked(apiFetch).mockResolvedValue(
      new Response(null, {
        status: 302,
        headers: { location: "https://gcs.test/f?sig=1" },
      }),
    );
    const res = await call();
    expect(res.status).toBe(302);
    expect(res.headers.get("location")).toBe("https://gcs.test/f?sig=1");
  });

  it("returns 502 for a 302 without Location", async () => {
    vi.mocked(apiFetch).mockResolvedValue(new Response(null, { status: 302 }));
    expect((await call()).status).toBe(502);
  });
});
