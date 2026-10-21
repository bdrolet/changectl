import { NextResponse } from "next/server";

import { ApiError, apiFetch } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  ctx: RouteContext<"/api/download/[revisionId]">,
) {
  const { revisionId } = await ctx.params;
  const requested = new URL(request.url).searchParams.get("which");
  const which = requested === "redline" ? "redline" : "released";

  try {
    const response = await apiFetch<Response>(
      `/revisions/${encodeURIComponent(revisionId)}/download?which=${which}`,
      { raw: true },
    );
    if (response.status === 401) {
      return NextResponse.redirect(new URL("/signin", request.url), 302);
    }
    if (response.status === 302) {
      const location = response.headers.get("location");
      if (!location) {
        return NextResponse.json(
          {
            detail: "bad_gateway",
            message: "Upstream redirect had no Location",
          },
          { status: 502 },
        );
      }
      return NextResponse.redirect(new URL(location, request.url), 302);
    }
    const body: unknown = await response.json().catch(() => ({}));
    return NextResponse.json(body, { status: response.status });
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      return NextResponse.redirect(new URL("/signin", request.url), 302);
    }
    throw e;
  }
}
