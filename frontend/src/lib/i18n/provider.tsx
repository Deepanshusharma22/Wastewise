"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { dictionary, type Dictionary } from "./dictionary";
import type { Bilingual, BilingualList, Lang } from "@/lib/types";

interface I18nValue {
  lang: Lang;
  t: Dictionary;
  setLang: (l: Lang) => void;
  /** Pick the active language from a bilingual value coming from the API/knowledge base. */
  pick: <T extends Bilingual | BilingualList>(v: T | null | undefined) => T extends BilingualList ? string[] : string;
}

const I18nContext = createContext<I18nValue | null>(null);
const STORAGE_KEY = "ww-lang";

export function I18nProvider({ children, initialLang = "en" }: { children: React.ReactNode; initialLang?: Lang }) {
  const [lang, setLangState] = useState<Lang>(initialLang);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "en" || stored === "hi") setLangState(stored);
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    window.localStorage.setItem(STORAGE_KEY, l);
    document.cookie = `${STORAGE_KEY}=${l}; path=/; max-age=31536000; samesite=lax`;
  }, []);

  const value = useMemo<I18nValue>(() => ({
    lang,
    t: dictionary[lang] as unknown as Dictionary,
    setLang,
    pick: ((v: Bilingual | BilingualList | null | undefined) => {
      if (!v) return (Array.isArray((v as unknown as BilingualList)?.en) ? [] : "") as never;
      const val = (v as Record<Lang, unknown>)[lang] ?? (v as Record<Lang, unknown>).en;
      return val as never;
    }) as I18nValue["pick"],
  }), [lang, setLang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}
