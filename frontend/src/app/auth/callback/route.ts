import { NextResponse, type NextRequest } from "next/server";
import { getServerSupabase } from "@/lib/supabase/server";
import { isLocalMode } from "@/lib/runtime-mode";

const API_URL = (process.env.API_URL || "http://localhost:8000").replace(/\/$/, "");

/**
 * Handles every e-mail link: confirmation, magic link and password recovery.
 *
 * Registered: `?code=` (Supabase PKCE) and `?token_hash=&type=` (Supabase OTP and
 * local mode). The old version only understood `?code=`, so a `token_hash` link fell
 * through to a hard-coded "link is invalid or has expired" — that was the login bug.
 *
 * Every failure mode now gets its own message and a way out (`/login?error=…&email=…`
 * renders a "send a new link" action instead of a dead end).
 */
/** Absolute origin of this request, honouring reverse proxies (e.g. preview hosts). */
function requestOrigin(request: NextRequest): string {
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  if (!host) return request.nextUrl.origin;
  const proto = request.headers.get("x-forwarded-proto") ?? request.nextUrl.protocol.replace(":", "");
  return `${proto}://${host}`;
}

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const origin = requestOrigin(request);
  const code = searchParams.get("code");
  const tokenHash = searchParams.get("token_hash");
  const type = searchParams.get("type");
  const rawNext = searchParams.get("next") ?? (type === "recovery" ? "/reset-password" : "/dashboard");
  const next = rawNext.startsWith("/") && !rawNext.startsWith("//") ? rawNext : "/dashboard";
  const emailHint = searchParams.get("email") ?? "";

  const fail = (code: string, message: string) => {
    const url = new URL("/login", origin);
    url.searchParams.set("error", message);
    url.searchParams.set("reason", code);
    if (emailHint) url.searchParams.set("email", emailHint);
    return NextResponse.redirect(url);
  };

  if (!code && !tokenHash) {
    return fail("missing_token", "This link is incomplete. Request a new one below.");
  }

  // ---- local mode: the API verifies the single-use link token and issues a JWT
  if (await isLocalMode()) {
    if (!tokenHash) return fail("unsupported_link", "This link is not valid for this deployment. Request a new one.");
    try {
      const res = await fetch(`${API_URL}/api/v1/auth/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: tokenHash }),
        cache: "no-store",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const c = body?.error?.code === "link_expired" ? "link_expired" : "invalid_link";
        const msg = c === "link_expired"
          ? "This link has expired. Send yourself a new one below."
          : "This link is invalid or was already used. Send yourself a new one below.";
        return fail(c, msg);
      }
      const data = await res.json();
      const target = new URL(next, origin);
      // The local session is handed to the browser once; the client stores it and
      // immediately replaces the URL (see LocalSessionBridge in Providers).
      target.searchParams.set("token", data.access_token);
      target.searchParams.set("email", data.user?.email ?? emailHint);
      return NextResponse.redirect(target);
    } catch {
      return fail("api_unreachable", "Could not reach the server. Please try again.");
    }
  }

  // ---- Supabase
  const supabase = await getServerSupabase();
  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) return NextResponse.redirect(new URL(next, origin));
    // A consumed/expired PKCE code is the most common failure; be specific.
    const expired = /expired|invalid|not found/i.test(error.message);
    return fail(expired ? "link_expired" : "exchange_failed",
      expired ? "This link has expired or was already used. Send yourself a new one below."
              : `Sign-in failed: ${error.message}`);
  }
  if (tokenHash && type) {
    const otpType = (["signup", "invite", "magiclink", "recovery", "email_change", "email"].includes(type) ? type : "email") as
      "signup" | "invite" | "magiclink" | "recovery" | "email_change" | "email";
    const { error } = await supabase.auth.verifyOtp({ token_hash: tokenHash, type: otpType });
    if (!error) return NextResponse.redirect(new URL(next, origin));
    return fail("link_expired",
      /expired/i.test(error.message)
        ? "This link has expired. Send yourself a new one below."
        : "This link is invalid or was already used. Send yourself a new one below.");
  }
  return fail("unsupported_link", "This link is not valid. Request a new one below.");
}
