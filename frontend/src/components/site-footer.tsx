"use client";

import Link from "next/link";
import { Logo } from "@/components/logo";
import { useI18n } from "@/lib/i18n/provider";

export function SiteFooter() {
  const { t } = useI18n();
  return (
    <footer className="mt-16 border-t bg-card/50">
      <div className="mx-auto grid max-w-6xl gap-6 px-4 py-8 text-sm text-muted-foreground md:grid-cols-[auto_1fr_auto] md:items-start">
        <Logo className="text-foreground" />
        <div className="space-y-1.5">
          <p>{t.footer.note}</p>
          <p className="text-xs">{t.footer.data}</p>
        </div>
        <nav className="flex gap-4" aria-label="Footer">
          <Link href="/guide" className="hover:text-foreground">{t.nav.guide}</Link>
          <a href="https://github.com/Madhurchaudhary/Wastewise" className="hover:text-foreground" target="_blank" rel="noreferrer">GitHub</a>
        </nav>
      </div>
    </footer>
  );
}
