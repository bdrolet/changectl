import "server-only";

import { headers as requestHeaders } from "next/headers";
import { getToken } from "next-auth/jwt";

import { auth } from "@/auth";

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
  init: RequestInit = {},
): Promise<T> {
  const session = await auth();
  if (!session || session.error) {
    throw new ApiError(401, "missing_bearer", "Not signed in");
  }
  // The ID token lives only in the encrypted JWT cookie; it is never copied
  // onto the session, which /api/auth/session serves to the browser.
  const token = await getToken({
    req: { headers: await requestHeaders() },
    secret: process.env.AUTH_SECRET,
    secureCookie: process.env.AUTH_URL?.startsWith("https") ?? false,
  });
  if (!token?.id_token) {
    throw new ApiError(401, "missing_bearer", "Not signed in");
  }

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token.id_token}`);
  if (init.body instanceof FormData) {
    headers.delete("Content-Type");
  } else {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${process.env.API_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

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
