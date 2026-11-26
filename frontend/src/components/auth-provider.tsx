"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { backend, type Backend, type BackendMode } from "@/lib/backend";
import { useI18n } from "@/lib/i18n/provider";
import type { Profile } from "@/lib/types";

interface AuthValue {
  user: { id: string; email: string | null } | null;
  profile: Profile | null;
  loading: boolean;
  mode: BackendMode | null;
  refreshProfile: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

/**
 * Session owner for both backends.
 *
 * In local mode the confirmation link redirects to `<next>?token=…`; this provider
 * picks that token up once, stores it, and rewrites the URL so it never shows in
 * history or gets shared. In Supabase mode the session lives in cookies and is
 * refreshed by middleware, so there is nothing to do but read it.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthValue["user"]>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<BackendMode | null>(null);
  const router = useRouter();
  const pathname = usePathname();
  const { setLang } = useI18n();
  const { setTheme } = useTheme();

  const loadProfile = useCallback(async (b: Backend) => {
    const p = await b.getProfile();
    setProfile(p);
    if (p && !sessionStorage.getItem("ww-prefs-applied")) {
      setLang(p.preferred_language);
      setTheme(p.theme);
      sessionStorage.setItem("ww-prefs-applied", "1");
    }
  }, [setLang, setTheme]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const b = await backend();
      if (cancelled) return;
      setMode(b.mode);

      // Local mode: consume a one-time token handed over by /auth/callback.
      if (b.mode === "local") {
        const params = new URLSearchParams(window.location.search);
        const token = params.get("token");
        if (token) {
          window.localStorage.setItem("ww-local-token", token);
          if (params.get("email")) {
            window.localStorage.setItem("ww-local-user", JSON.stringify({ id: "", email: params.get("email") }));
          }
          params.delete("token");
          params.delete("email");
          const q = params.toString();
          window.history.replaceState({}, "", window.location.pathname + (q ? `?${q}` : ""));
          if (b instanceof Object && "reload" in b && typeof (b as { reload?: () => void }).reload === "function") {
            (b as unknown as { reload: () => void }).reload();
          }
        }
      }

      const session = await b.session();
      setUser(session);
      if (session) await loadProfile(b);
      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, [loadProfile]);

  // Re-read the session after any client navigation (cheap, and keeps cookies in sync).
  useEffect(() => {
    (async () => {
      const b = await backend();
      const s = await b.session();
      setUser((prev) => (prev?.id === s?.id ? prev : s));
    })();
  }, [pathname]);

  const value: AuthValue = {
    user, profile, loading, mode,
    refreshProfile: async () => { const b = await backend(); await loadProfile(b); },
    signOut: async () => {
      const b = await backend();
      await b.logout();
      setUser(null);
      setProfile(null);
      sessionStorage.removeItem("ww-prefs-applied");
      router.push("/");
      router.refresh();
    },
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
