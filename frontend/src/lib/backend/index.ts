"use client";

/**
 * One auth/data interface, two implementations.
 *
 *  - `SupabaseBackend`  – production: Supabase Auth + Postgres (RLS) + Storage.
 *  - `LocalBackend`     – used when the API reports `LOCAL_MODE` (see `detectMode()`).
 *                         Auth + profile + avatar go through the API, which stores
 *                         everything in SQLite/filesystem. No email server is involved,
 *                         so confirmation links are handed to the UI directly.
 *
 * Components never talk to Supabase directly any more; they call `backend()`.
 */
import { supabaseConfigured, getSupabase } from "@/lib/supabase/client";
import type { Profile, Lang } from "@/lib/types";

export type BackendMode = "supabase" | "local";

export interface Axios { name: string; message: string }

export interface SignupInput { email: string; password: string; fullName: string; emailRedirectTo: string }
export interface SignupResult {
  needsConfirmation: boolean;
  user: { id: string; email: string } | null;
  /** Local mode only: the confirmation URL that would have been emailed. */
  emailLink: string | null;
  debugToken: string | null;
  error: Axios | null;
}
export interface AuthResult { user: { id: string; email: string | null } | null; error: Axios | null }

export interface Backend {
  mode: BackendMode;
  /** Absolute URL the mail should redirect back to (frontend callback route). */
  callbackUrl(next: string): string;

  session(): Promise<{ id: string; email: string | null } | null>;
  signup(i: SignupInput): Promise<SignupResult>;
  login(email: string, password: string): Promise<AuthResult>;
  logout(): Promise<void>;
  /** Exchange the tokens a mail link carries. Never throws on failure. */
  completeLink(params: { code?: string | null; tokenHash?: string | null; type?: string | null }): Promise<AuthResult>;
  /** 6-digit code fallback (Supabase only; local links are single-use URLs). */
  verifyCode(email: string, code: string, type: "signup" | "recovery"): Promise<AuthResult>;
  resendConfirmation(email: string, emailRedirectTo: string): Promise<{ ok: boolean; emailLink: string | null; alreadyConfirmed: boolean }>;
  requestReset(email: string, emailRedirectTo: string): Promise<{ ok: boolean; emailLink: string | null }>;
  updatePassword(password: string): Promise<Axios | null>;

  getProfile(): Promise<Profile | null>;
  updateProfile(patch: Partial<Pick<Profile, "full_name" | "preferred_language" | "theme" | "save_images">>): Promise<Axios | null>;
  uploadAvatar(file: File): Promise<{ avatarUrl: string | null; error: Axios | null }>;
  signedAvatarUrl(path: string | null): Promise<string | null>;
}

/** Detects the API mode. Cached for the tab; defaults to Supabase when offline. */
let modePromise: Promise<BackendMode> | null = null;

export function detectMode(): Promise<BackendMode> {
  if (modePromise) return modePromise;
  modePromise = (async () => {
    try {
      const res = await fetch("/api/v1/local-info", { cache: "no-store" });
      if (res.ok) return "local";
    } catch { /* network problem: assume the production configuration */ }
    return "supabase";
  })();
  return modePromise;
}

function cb(next: string): string {
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  return `${origin}/auth/callback?next=${encodeURIComponent(next)}`;
}

const PROFILE_COLUMNS = "id, full_name, email, avatar_url, preferred_language, theme, save_images";

// ---------------------------------------------------------------- Supabase (production)
class SupabaseBackend implements Backend {
  readonly mode = "supabase" as const;
  private sb = () => getSupabase();

  callbackUrl(next: string) { return cb(next); }

  async session() {
    const { data } = await this.sb().auth.getSession();
    const u = data.session?.user;
    return u ? { id: u.id, email: u.email ?? null } : null;
  }

  async signup(i: SignupInput): Promise<SignupResult> {
    const { data, error } = await this.sb().auth.signUp({
      email: i.email.trim(),
      password: i.password,
      options: { data: { full_name: i.fullName.trim() }, emailRedirectTo: i.emailRedirectTo },
    });
    if (error) return { needsConfirmation: false, user: null, emailLink: null, debugToken: null, error: { name: "signup", message: error.message } };
    if (data.session) return { needsConfirmation: false, user: { id: data.user!.id, email: data.user!.email ?? "" }, emailLink: null, debugToken: null, error: null };
    return {
      needsConfirmation: true,
      user: data.user ? { id: data.user.id, email: data.user.email ?? "" } : null,
      emailLink: null, debugToken: null, error: null,
    };
  }

  async login(email: string, password: string): Promise<AuthResult> {
    const { data, error } = await this.sb().auth.signInWithPassword({ email: email.trim(), password });
    if (error) return { user: null, error: { name: "login", message: error.message } };
    return { user: { id: data.user.id, email: data.user.email ?? null }, error: null };
  }

  async logout() { await this.sb().auth.signOut(); }

  async completeLink({ code, tokenHash, type }: { code?: string | null; tokenHash?: string | null; type?: string | null }): Promise<AuthResult> {
    try {
      if (code) {
        const { data, error } = await this.sb().auth.exchangeCodeForSession(code);
        if (error) return { user: null, error: { name: "exchange", message: error.message } };
        return { user: data.user ? { id: data.user.id, email: data.user.email ?? null } : null, error: null };
      }
      if (tokenHash && type) {
        const otpType = (["signup", "invite", "magiclink", "recovery", "email_change", "email"].includes(type) ? type : "email") as
          "signup" | "invite" | "magiclink" | "recovery" | "email_change" | "email";
        const { data, error } = await this.sb().auth.verifyOtp({ token_hash: tokenHash, type: otpType });
        if (error) return { user: null, error: { name: "verifyOtp", message: error.message } };
        return { user: data.user ? { id: data.user.id, email: data.user.email ?? null } : null, error: null };
      }
      return { user: null, error: { name: "no_token", message: "This link is missing its token." } };
    } catch (e) {
      return { user: null, error: { name: "unknown", message: e instanceof Error ? e.message : "Unknown error" } };
    }
  }

  async verifyCode(email: string, token: string, type: "signup" | "recovery"): Promise<AuthResult> {
    const { data, error } = await this.sb().auth.verifyOtp({ email: email.trim(), token: token.trim(), type });
    if (error) return { user: null, error: { name: "verifyOtp", message: error.message } };
    return { user: data.user ? { id: data.user.id, email: data.user.email ?? null } : null, error: null };
  }

  async resendConfirmation(email: string, emailRedirectTo: string) {
    const { error } = await this.sb().auth.resend({ type: "signup", email: email.trim(), options: { emailRedirectTo } });
    const msg = error?.message ?? "";
    return { ok: !error, emailLink: null, alreadyConfirmed: /already|confirmed/i.test(msg) };
  }

  async requestReset(email: string, emailRedirectTo: string) {
    const { error } = await this.sb().auth.resetPasswordForEmail(email.trim(), { redirectTo: emailRedirectTo });
    return { ok: !error, emailLink: null };
  }

  async updatePassword(password: string): Promise<Axios | null> {
    const { error } = await this.sb().auth.updateUser({ password });
    return error ? { name: "updateUser", message: error.message } : null;
  }

  async getProfile(): Promise<Profile | null> {
    const s = await this.session();
    if (!s) return null;
    const { data } = await this.sb().from("profiles").select(PROFILE_COLUMNS).eq("id", s.id).maybeSingle();
    return (data as Profile) ?? null;
  }

  async updateProfile(patch: Partial<Pick<Profile, "full_name" | "preferred_language" | "theme" | "save_images">>): Promise<Axios | null> {
    const s = await this.session();
    if (!s) return { name: "auth", message: "Not signed in" };
    const { error } = await this.sb().from("profiles").update(patch).eq("id", s.id);
    return error ? { name: "update", message: error.message } : null;
  }

  async uploadAvatar(file: File) {
    const s = await this.session();
    if (!s) return { avatarUrl: null, error: { name: "auth", message: "Not signed in" } };
    const { uploadAvatar: helper } = await import("@/lib/avatar");
    return helper(file, { mode: "supabase", userId: s.id });
  }

  async signedAvatarUrl(path: string | null): Promise<string | null> {
    if (!path) return null;
    const { data } = await this.sb().storage.from("avatars").createSignedUrl(path, 3600);
    return data?.signedUrl ?? null;
  }
}

// ---------------------------------------------------------------- Local (no Supabase)
class LocalBackend implements Backend {
  readonly mode = "local" as const;
  private token: string | null = null;
  private user: { id: string; email: string | null } | null = null;

  constructor() {
    this.reload();
  }

  /** Re-read the token written by the provider after a confirmation link. */
  reload() {
    if (typeof window === "undefined") return;
    this.token = window.localStorage.getItem("ww-local-token");
    const raw = window.localStorage.getItem("ww-local-user");
    if (raw) { try { this.user = JSON.parse(raw); } catch { /* ignore */ } }
  }

  callbackUrl(next: string) { return cb(next); }

  private save(token: string | null, user: { id: string; email: string | null } | null) {
    this.token = token; this.user = user;
    if (typeof window === "undefined") return;
    if (token) window.localStorage.setItem("ww-local-token", token);
    else window.localStorage.removeItem("ww-local-token");
    if (user) window.localStorage.setItem("ww-local-user", JSON.stringify(user));
    else window.localStorage.removeItem("ww-local-user");
  }

  private async post<T>(path: string, body: unknown, auth = false): Promise<T> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (auth && this.token) headers.Authorization = `Bearer ${this.token}`;
    const res = await fetch(`/api/v1${path}`, { method: "POST", headers, body: JSON.stringify(body) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.error?.message ?? `Request failed (${res.status})`);
    return data as T;
  }

  async session() {
    if (!this.token) return null;
    // A link hand-over only knows the email; recover the real id from the API.
    if (!this.user?.id) {
      const p = await this.getProfile();
      if (!p) { this.save(null, null); return null; }
      this.save(this.token, { id: p.id, email: p.email ?? this.user?.email ?? null });
    }
    return this.user;
  }

  async signup(i: SignupInput): Promise<SignupResult> {
    try {
      const data = await this.post<{
        needs_confirmation: boolean; email_link: string | null; debug_token: string | null;
        access_token?: string; user: { id: string; email: string };
      }>("/auth/signup", { email: i.email, password: i.password, full_name: i.fullName, redirect_to: i.emailRedirectTo });
      if (data.needs_confirmation) {
        return { needsConfirmation: true, user: data.user ?? null, emailLink: data.email_link, debugToken: data.debug_token, error: null };
      }
      this.save(data.access_token ?? null, data.user);
      return { needsConfirmation: false, user: data.user, emailLink: null, debugToken: null, error: null };
    } catch (e) {
      return { needsConfirmation: false, user: null, emailLink: null, debugToken: null, error: { name: "signup", message: (e as Error).message } };
    }
  }

  async login(email: string, password: string): Promise<AuthResult> {
    try {
      const data = await this.post<{ access_token: string; user: { id: string; email: string } }>("/auth/login", { email, password });
      this.save(data.access_token, data.user);
      return { user: data.user, error: null };
    } catch (e) {
      return { user: null, error: { name: "login", message: (e as Error).message } };
    }
  }

  async logout() {
    try { await this.post("/auth/logout", {}, true); } catch { /* stateless */ }
    this.save(null, null);
  }

  async completeLink({ code, tokenHash, type }: { code?: string | null; tokenHash?: string | null; type?: string | null }): Promise<AuthResult> {
    // `code` is only produced by Supabase; local links always carry token_hash.
    if (!tokenHash) return { user: null, error: { name: "no_token", message: "This link has no token." } };
    try {
      const isRecovery = type === "recovery";
      const data = await this.post<{ access_token: string; user: { id: string; email: string } }>("/auth/confirm", { token: tokenHash });
      this.save(data.access_token, data.user);
      if (isRecovery) return { user: { ...data.user, recovery: true } as unknown as { id: string; email: string | null }, error: null };
      return { user: data.user, error: null };
    } catch (e) {
      return { user: null, error: { name: "confirm", message: (e as Error).message } };
    }
    void code;
  }

  async verifyCode(): Promise<AuthResult> {
    return { user: null, error: { name: "unsupported", message: "Codes are not used in local mode — open the confirmation link instead." } };
  }

  async resendConfirmation(email: string, emailRedirectTo: string) {
    try {
      const data = await this.post<{ sent: boolean; already_confirmed?: boolean; email_link: string | null }>(
        "/auth/resend", { email, redirect_to: emailRedirectTo });
      return { ok: data.sent, emailLink: data.email_link, alreadyConfirmed: Boolean(data.already_confirmed) };
    } catch {
      return { ok: false, emailLink: null, alreadyConfirmed: false };
    }
  }

  async requestReset(email: string, emailRedirectTo: string) {
    try {
      const data = await this.post<{ sent: boolean; email_link: string | null }>("/auth/recover", { email, redirect_to: emailRedirectTo });
      return { ok: data.sent, emailLink: data.email_link };
    } catch {
      return { ok: false, emailLink: null };
    }
  }

  async updatePassword(password: string): Promise<Axios | null> {
    try { await this.post("/auth/password", { password }, true); return null; }
    catch (e) { return { name: "password", message: (e as Error).message }; }
  }

  async getProfile(): Promise<Profile | null> {
    if (!this.token) return null;
    const res = await fetch("/api/v1/profile", { headers: { Authorization: `Bearer ${this.token}` }, cache: "no-store" });
    if (!res.ok) return null;
    const d = await res.json();
    return { ...d, avatar_signed_url: d.avatar_url_signed ?? null } as Profile;
  }

  async updateProfile(patch: Partial<Pick<Profile, "full_name" | "preferred_language" | "theme" | "save_images">>): Promise<Axios | null> {
    if (!this.token) return { name: "auth", message: "Not signed in" };
    const res = await fetch("/api/v1/profile", {
      method: "PATCH",
      headers: { Authorization: `Bearer ${this.token}`, "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      return { name: "update", message: d?.error?.message ?? "Could not save" };
    }
    return null;
  }

  async uploadAvatar(file: File) {
    if (!this.token) return { avatarUrl: null, error: { name: "auth", message: "Not signed in" } };
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/v1/profile/avatar", { method: "PUT", headers: { Authorization: `Bearer ${this.token}` }, body: fd });
    const d = await res.json().catch(() => ({}));
    if (!res.ok) return { avatarUrl: null, error: { name: "upload", message: d?.error?.message ?? "Upload failed" } };
    return { avatarUrl: d.avatar_url_signed ?? null, error: null };
  }

  async signedAvatarUrl(path: string | null): Promise<string | null> {
    if (!path) return null;
    return `/files/avatars/${path}`;
  }
}

let instance: Backend | null = null;

/** Resolves once: local API mode or Supabase. */
export async function backend(): Promise<Backend> {
  if (instance) return instance;
  const mode = await detectMode();
  instance = mode === "local" ? new LocalBackend() : new SupabaseBackend();
  if (mode === "supabase" && !supabaseConfigured()) {
    console.warn("Supabase is not configured and the API is not in local mode: auth will not work.");
  }
  return instance;
}

export function languageForProfile(p: Profile | null): Lang {
  return p?.preferred_language === "hi" ? "hi" : "en";
}
