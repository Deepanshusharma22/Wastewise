import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

const API_URL = (process.env.API_URL || "http://localhost:8000").replace(/\/$/, "");
const PROTECTED = ["/dashboard", "/analyze", "/result", "/history", "/analytics", "/settings"];

/**
 * The route guard is Supabase-specific. In LOCAL_MODE the API does not own the
 * session cookie, so guarding here would bounce every local user to /login — the
 * client provider handles access instead.
 */
async function apiIsLocal(): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/api/v1/local-info`, { cache: "no-store", signal: AbortSignal.timeout(1500) });
    return res.ok;
  } catch {
    return false;
  }
}
const AUTH_PAGES = ["/login", "/signup"];

/** Refreshes the Supabase session cookie and guards app routes. */
export async function middleware(request: NextRequest) {
  let response = NextResponse.next({ request });
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (await apiIsLocal()) return response;     // local demo mode: no Supabase session to refresh
  if (!url || !key) return response;

  const supabase = createServerClient(url, key, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (list) => {
        list.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        list.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
      },
    },
  });

  const { data: { user } } = await supabase.auth.getUser();
  const path = request.nextUrl.pathname;

  if (!user && PROTECTED.some((p) => path === p || path.startsWith(`${p}/`))) {
    const to = request.nextUrl.clone();
    to.pathname = "/login";
    to.search = `?next=${encodeURIComponent(path + request.nextUrl.search)}`;
    return NextResponse.redirect(to);
  }
  if (user && AUTH_PAGES.includes(path)) {
    const to = request.nextUrl.clone();
    to.pathname = "/dashboard";
    to.search = "";
    return NextResponse.redirect(to);
  }
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|icon.svg|api/|.*\\.(?:png|jpg|jpeg|svg|webp|ico)$).*)"],
};
