import NextAuth, { type NextAuthConfig } from "next-auth";
import Google from "next-auth/providers/google";

import type { UserOut } from "@/lib/types";

declare module "next-auth" {
  interface Session {
    error?: "RefreshFailed";
    user: {
      id: string;
      role: string;
      isDocManager: boolean;
      name: string;
      email: string;
    };
  }
}

declare module "@auth/core/jwt" {
  interface JWT {
    id_token?: string;
    refresh_token?: string;
    expires_at?: number;
    user?: UserOut;
    error?: "RefreshFailed";
  }
}

export const authConfig: NextAuthConfig = {
  providers: [Google],
  session: { strategy: "jwt", maxAge: 8 * 60 * 60 },
  pages: { signIn: "/signin" },
  callbacks: {
    async signIn({ account }) {
      if (!account?.id_token) return "/signin?error=api";
      let response: Response;
      try {
        response = await fetch(`${process.env.API_URL}/me`, {
          headers: { Authorization: `Bearer ${account.id_token}` },
          cache: "no-store",
        });
      } catch {
        return "/signin?error=api";
      }
      if (response.status === 403) return "/not-invited";
      if (response.status !== 200) return "/signin?error=api";
      // Cached on the token in the jwt callback below.
      (account as { user?: UserOut }).user = (await response.json()) as UserOut;
      return true;
    },
    async jwt({ token, account }) {
      if (account) {
        token.id_token = account.id_token;
        token.refresh_token = account.refresh_token;
        token.expires_at = account.expires_at;
        token.user = (account as { user?: UserOut }).user;
        delete token.error;
        return token;
      }
      if (
        token.expires_at !== undefined &&
        Date.now() / 1000 > token.expires_at - 60
      ) {
        try {
          const response = await fetch("https://oauth2.googleapis.com/token", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({
              client_id: process.env.AUTH_GOOGLE_ID ?? "",
              client_secret: process.env.AUTH_GOOGLE_SECRET ?? "",
              grant_type: "refresh_token",
              refresh_token: token.refresh_token ?? "",
            }),
          });
          const data = await response.json();
          if (!response.ok || !data.id_token) throw new Error("refresh failed");
          token.id_token = data.id_token;
          token.expires_at = Math.floor(Date.now() / 1000) + data.expires_in;
          if (data.refresh_token) token.refresh_token = data.refresh_token;
          delete token.error;
        } catch {
          token.error = "RefreshFailed";
        }
      }
      return token;
    },
    async session({ session, token }) {
      const user = token.user;
      if (user) {
        session.user.id = user.id;
        session.user.role = user.role;
        session.user.isDocManager = user.is_doc_manager;
        session.user.name = user.name;
        session.user.email = user.email;
      }
      if (token.error) session.error = token.error;
      return session;
    },
  },
};

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig);
