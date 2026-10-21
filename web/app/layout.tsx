import type { Metadata } from "next";
import Link from "next/link";

import { auth, signOut } from "@/auth";
import "./globals.css";

export const metadata: Metadata = {
  title: "changectl",
  description: "Change control for controlled documents",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const session = await auth();
  const user = session?.user;

  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-white text-zinc-900">
        {user && (
          <header className="border-b border-zinc-200">
            <nav className="mx-auto flex max-w-5xl items-center gap-6 px-4 py-3 text-sm">
              <Link href="/changes" className="font-semibold text-blue-700">
                changectl
              </Link>
              <Link href="/changes" className="hover:text-blue-700">
                Changes
              </Link>
              <Link href="/documents" className="hover:text-blue-700">
                Documents
              </Link>
              {user.isDocManager && (
                <Link href="/users" className="hover:text-blue-700">
                  Users
                </Link>
              )}
              <span className="ml-auto text-zinc-600">{user.name}</span>
              <form
                action={async () => {
                  "use server";
                  await signOut({ redirectTo: "/signin" });
                }}
              >
                <button
                  type="submit"
                  className="rounded border border-zinc-300 px-3 py-1 hover:bg-zinc-50"
                >
                  Sign out
                </button>
              </form>
            </nav>
          </header>
        )}
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
