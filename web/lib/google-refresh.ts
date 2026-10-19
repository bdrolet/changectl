export interface RefreshedToken {
  id_token: string;
  expires_at: number;
  refresh_token?: string;
}

/** Exchange a Google refresh token for a fresh ID token. Throws on failure. */
export async function refreshGoogleToken(
  refreshToken: string,
): Promise<RefreshedToken> {
  const response = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: process.env.AUTH_GOOGLE_ID ?? "",
      client_secret: process.env.AUTH_GOOGLE_SECRET ?? "",
      grant_type: "refresh_token",
      refresh_token: refreshToken,
    }),
  });
  const data = await response.json();
  if (!response.ok || !data.id_token) throw new Error("refresh failed");
  return {
    id_token: data.id_token,
    expires_at: Math.floor(Date.now() / 1000) + data.expires_in,
    refresh_token: data.refresh_token,
  };
}

export function isExpired(expiresAt: number | undefined | null): boolean {
  return expiresAt != null && Date.now() / 1000 > expiresAt - 60;
}
