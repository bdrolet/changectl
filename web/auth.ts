import NextAuth, { type NextAuthConfig } from "next-auth";
import Google from "next-auth/providers/google";

import { isExpired, refreshGoogleToken } from "@/lib/google-refresh";
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
  providers: [
    Google({
      authorization: {
        params: { access_type: "offline", prompt: "select_account consent" },
      },
    }),
  ],
  session: { strategy: "jwt", maxAge: 8 * 60 * 60 },
  pages: { signIn: "/signin" },
  callbacks: {
    async signIn({ account, profile }) {
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
      if (response.status === 403) {
        const email = typeof profile?.email === "string" ? profile.email : "";
        return email
          ? `/not-invited?email=${encodeURIComponent(email)}`
          : "/not-invited";
      }
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
      if (!token.error && isExpired(token.expires_at)) {
        try {
          const fresh = await refreshGoogleToken(token.refresh_token ?? "");
          token.id_token = fresh.id_token;
          token.expires_at = fresh.expires_at;
          if (fresh.refresh_token) token.refresh_token = fresh.refresh_token;
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
