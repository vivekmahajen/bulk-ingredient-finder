import { NextResponse, type NextRequest } from "next/server";

/**
 * Edge guard for `/dashboard/**`. The access/refresh cookies are httpOnly, but
 * middleware runs server-side so it can still read them. If neither is present we
 * bounce to /login (preserving the intended path). The API remains the real
 * security boundary — this is a UX redirect, not the authorization check.
 */
export function middleware(req: NextRequest) {
  const hasSession = req.cookies.has("rr_access") || req.cookies.has("rr_refresh");
  if (!hasSession) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", req.nextUrl.pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
