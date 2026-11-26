"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { BarChart3, BookOpen, History, LayoutDashboard, LogOut, Menu, ScanLine, Settings, X } from "lucide-react";
import { Logo } from "@/components/logo";
import { LanguageToggle, ThemeToggle } from "@/components/toggles";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/components/auth-provider";
import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

export function SiteHeader() {
  const { t } = useI18n();
  const { user, signOut, loading } = useAuth();
  const path = usePathname();
  const [open, setOpen] = useState(false);

  const links = user
    ? [
        { href: "/dashboard", label: t.nav.dashboard, icon: LayoutDashboard },
        { href: "/analyze", label: t.nav.analyze, icon: ScanLine },
        { href: "/history", label: t.nav.history, icon: History },
        { href: "/analytics", label: t.nav.analytics, icon: BarChart3 },
        { href: "/guide", label: t.nav.guide, icon: BookOpen },
      ]
    : [{ href: "/guide", label: t.nav.guide, icon: BookOpen }];

  const isActive = (href: string) => path === href || path.startsWith(`${href}/`);

  return (
    <header className="sticky top-0 z-40 border-b bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2">
        {t.nav.skip}
      </a>
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4">
        <Link href={user ? "/dashboard" : "/"} aria-label="WasteWise home"><Logo /></Link>
        <nav className="ml-4 hidden items-center gap-1 md:flex" aria-label="Main">
          {links.map((l) => (
            <Link key={l.href} href={l.href} aria-current={isActive(l.href) ? "page" : undefined}
              className={cn("rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
                isActive(l.href) && "bg-accent text-accent-foreground")}>
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-1">
          <LanguageToggle />
          <ThemeToggle />
          {!loading && (user ? (
            <div className="hidden items-center gap-1 md:flex">
              <Button asChild variant="ghost" size="icon" aria-label={t.nav.settings}><Link href="/settings"><Settings /></Link></Button>
              <Button variant="outline" size="sm" onClick={signOut}><LogOut />{t.nav.logout}</Button>
            </div>
          ) : (
            <div className="hidden items-center gap-2 md:flex">
              <Button asChild variant="ghost" size="sm"><Link href="/login">{t.nav.login}</Link></Button>
              <Button asChild size="sm"><Link href="/signup">{t.nav.signup}</Link></Button>
            </div>
          ))}
          <Button variant="ghost" size="icon" className="md:hidden" aria-label={t.nav.menu} aria-expanded={open} onClick={() => setOpen((o) => !o)}>
            {open ? <X /> : <Menu />}
          </Button>
        </div>
      </div>
      {open && (
        <nav className="border-t bg-background px-4 py-3 md:hidden" aria-label="Mobile">
          <ul className="flex flex-col gap-1">
            {links.map((l) => (
              <li key={l.href}>
                <Link href={l.href} onClick={() => setOpen(false)} className={cn("flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium", isActive(l.href) && "bg-accent")}>
                  <l.icon className="h-4 w-4" />{l.label}
                </Link>
              </li>
            ))}
            {user ? (
              <>
                <li><Link href="/settings" onClick={() => setOpen(false)} className="flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium"><Settings className="h-4 w-4" />{t.nav.settings}</Link></li>
                <li><button onClick={() => { setOpen(false); void signOut(); }} className="flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium"><LogOut className="h-4 w-4" />{t.nav.logout}</button></li>
              </>
            ) : (
              <li className="flex gap-2 pt-2">
                <Button asChild variant="outline" className="flex-1"><Link href="/login" onClick={() => setOpen(false)}>{t.nav.login}</Link></Button>
                <Button asChild className="flex-1"><Link href="/signup" onClick={() => setOpen(false)}>{t.nav.signup}</Link></Button>
              </li>
            )}
          </ul>
        </nav>
      )}
    </header>
  );
}
