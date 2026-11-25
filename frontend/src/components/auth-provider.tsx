"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { User } from "@supabase/supabase-js";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { getSupabase, supabaseConfigured } from "@/lib/supabase/client";
import { useI18n } from "@/lib/i18n/provider";
import type { Profile } from "@/lib/types";

interface AuthValue {
  user: User | null;
  profile: Profile | null;
  loading: boolean;
  refreshProfile: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const { setLang } = useI18n();
  const { setTheme } = useTheme();

  const loadProfile = useCallback(async (u: User | null) => {
    if (!u) { setProfile(null); return; }
    const { data } = await getSupabase()
      .from("profiles")
      .select("id, full_name, email, avatar_url, preferred_language, theme, save_images")
      .eq("id", u.id)
      .maybeSingle();
    if (data) {
      setProfile(data as Profile);
      // apply saved preferences once per session (user can still toggle locally)
      if (!sessionStorage.getItem("ww-prefs-applied")) {
        setLang((data as Profile).preferred_language);
        setTheme((data as Profile).theme);
        sessionStorage.setItem("ww-prefs-applied", "1");
      }
    }
  }, [setLang, setTheme]);

  useEffect(() => {
    if (!supabaseConfigured()) { setLoading(false); return; }
    const sb = getSupabase();
    sb.auth.getUser().then(async ({ data }) => {
      setUser(data.user);
      await loadProfile(data.user);
      setLoading(false);
    });
    const { data: sub } = sb.auth.onAuthStateChange((event, session) => {
      setUser(session?.user ?? null);
      if (event === "SIGNED_IN" || event === "USER_UPDATED") void loadProfile(session?.user ?? null);
      if (event === "SIGNED_OUT") { setProfile(null); sessionStorage.removeItem("ww-prefs-applied"); }
    });
    return () => sub.subscription.unsubscribe();
  }, [loadProfile]);

  const value: AuthValue = {
    user, profile, loading,
    refreshProfile: () => loadProfile(user),
    signOut: async () => {
      await getSupabase().auth.signOut();
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
