import { NextResponse } from "next/server";

import { auth } from "@/auth";

const PUBLIC = ["/signin", "/not-invited"];

export const proxy = auth((req) => {
  const { pathname } = req.nextUrl;
  if (PUBLIC.includes(pathname)) return NextResponse.next();
  if (!req.auth || req.auth.error) {
    return NextResponse.redirect(new URL("/signin", req.nextUrl.origin));
  }
  return NextResponse.next();
});

export const config = {
  matcher: [
    "/((?!api/auth|_next/static|_next/image|favicon\\.ico|icon\\.svg).*)",
  ],
};
