"use client";

import { Languages, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n/provider";

export function LanguageToggle() {
  const { lang, setLang, t } = useI18n();
  return (
    <Button variant="ghost" size="sm" onClick={() => setLang(lang === "en" ? "hi" : "en")} aria-label={t.common.language} title={t.common.language}>
      <Languages />
      <span className="font-semibold">{lang === "en" ? "हिं" : "EN"}</span>
    </Button>
  );
}

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const { t } = useI18n();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const dark = mounted && resolvedTheme === "dark";
  return (
    <Button variant="ghost" size="icon" onClick={() => setTheme(dark ? "light" : "dark")} aria-label={t.common.theme} title={t.common.theme}>
      {dark ? <Sun /> : <Moon />}
    </Button>
  );
}
