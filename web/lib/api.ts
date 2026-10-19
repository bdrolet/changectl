import "server-only";

import { headers as requestHeaders } from "next/headers";
import { getToken } from "next-auth/jwt";

import { auth } from "@/auth";
import { isExpired, refreshGoogleToken } from "@/lib/google-refresh";

export class ApiError extends Error {
  status: number;
  detail: string;
  changes?: string[];

  constructor(
    status: number,
    detail: string,
    message: string,
    changes?: string[],
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.changes = changes;
  }
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit & { raw?: boolean } = {},
): Promise<T> {
  const session = await auth();
  if (!session || session.error) {
    throw new ApiError(401, "missing_bearer", "Not signed in");
  }
  // The ID token lives only in the encrypted JWT cookie; it is never copied
  // onto the session, which /api/auth/session serves to the browser.
  const reqHeaders = await requestHeaders();
  const proto = reqHeaders.get("x-forwarded-proto");
  const secure =
    proto !== null
      ? proto.split(",")[0].trim() === "https"
      : (process.env.AUTH_URL?.startsWith("https") ?? false);
  let token = null;
  for (const secureCookie of [secure, !secure]) {
    token = await getToken({
      req: { headers: reqHeaders },
      secret: process.env.AUTH_SECRET,
      secureCookie,
    });
    if (token) break;
  }
  if (!token?.id_token) {
    throw new ApiError(401, "missing_bearer", "Not signed in");
  }
  let idToken = token.id_token;
  if (isExpired(token.expires_at) && token.refresh_token) {
    // The proxy's refreshed cookie only reaches the response; this request
    // still carries the stale one, so refresh in memory for this call.
    try {
      idToken = (await refreshGoogleToken(token.refresh_token)).id_token;
    } catch {
      throw new ApiError(401, "invalid_token", "Session expired");
    }
  }

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${idToken}`);
  if (init.body instanceof FormData) {
    headers.delete("Content-Type");
  } else {
    headers.set("Content-Type", "application/json");
  }

  const { raw, ...rest } = init;
  const response = await fetch(`${process.env.API_URL}${path}`, {
    ...rest,
    headers,
    cache: "no-store",
    ...(raw ? { redirect: "manual" as const } : {}),
  });

  if (raw) return response as T;

  if (!response.ok) {
    let body: { detail?: unknown; message?: unknown; changes?: unknown };
    try {
      body = await response.json();
    } catch {
      body = {};
    }
    const detail =
      typeof body.detail === "string" ? body.detail : `http_${response.status}`;
    const message =
      typeof body.message === "string" ? body.message : response.statusText;
    const changes = Array.isArray(body.changes)
      ? body.changes.map(String)
      : undefined;
    throw new ApiError(response.status, detail, message, changes);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
