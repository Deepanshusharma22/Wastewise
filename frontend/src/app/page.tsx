"use client";

import Link from "next/link";
import { ArrowRight, BookOpen, Eye, ScanLine, ShieldCheck, Upload, Sparkles, Trash2, AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CategoryIcon } from "@/components/category-icon";
import { useAuth } from "@/components/auth-provider";
import { useI18n } from "@/lib/i18n/provider";
import { knowledge } from "@/lib/knowledge";
import { CATEGORIES } from "@/lib/types";

const STEP_ICONS = [Upload, Sparkles, Eye, Trash2];

export default function Landing() {
  const { t, pick } = useI18n();
  const { user } = useAuth();
  return (
    <>
      <section className="relative overflow-hidden bg-forest text-white">
        <div className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 rounded-full bg-primary/40 blur-3xl" aria-hidden />
        <div className="pointer-events-none absolute -bottom-32 -left-16 h-80 w-80 rounded-full bg-lime/20 blur-3xl" aria-hidden />
        <div className="relative mx-auto grid max-w-6xl gap-10 px-4 py-16 md:grid-cols-[1.2fr_1fr] md:py-24">
          <div className="animate-fade-up">
            <Badge className="bg-lime/20 text-lime">{t.landing.badge}</Badge>
            <h1 className="mt-5 text-4xl font-extrabold leading-tight tracking-tight md:text-5xl">{t.landing.title}</h1>
            <p className="mt-5 max-w-xl text-lg text-white/80">{t.landing.subtitle}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button asChild size="lg" variant="lime"><Link href={user ? "/analyze" : "/signup"}><ScanLine />{t.landing.ctaPrimary}<ArrowRight /></Link></Button>
              <Button asChild size="lg" variant="outline" className="border-white/30 bg-transparent text-white hover:bg-white/10 hover:text-white"><Link href="/guide"><BookOpen />{t.landing.ctaSecondary}</Link></Button>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 self-center" aria-hidden>
            {CATEGORIES.slice(0, 6).map((c, i) => (
              <div key={c} className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 p-4 backdrop-blur animate-fade-up" style={{ animationDelay: `${i * 60}ms` }}>
                <CategoryIcon category={c} boxed className="h-10 w-10 bg-white/90!" />
                <span className="text-sm font-medium">{t.categories[c]}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-16">
        <h2 className="text-2xl font-bold tracking-tight md:text-3xl">{t.landing.howTitle}</h2>
        <ol className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {t.landing.steps.map((s, i) => {
            const Icon = STEP_ICONS[i];
            return (
              <li key={s.t}>
                <Card className="h-full">
                  <CardContent className="pt-5">
                    <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-accent-foreground"><Icon className="h-5 w-5" aria-hidden /></span>
                    <h3 className="mt-4 font-semibold"><span className="text-primary">{i + 1}.</span> {s.t}</h3>
                    <p className="mt-1.5 text-sm text-muted-foreground">{s.d}</p>
                  </CardContent>
                </Card>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="border-y bg-card/60">
        <div className="mx-auto max-w-6xl px-4 py-16">
          <h2 className="text-2xl font-bold tracking-tight md:text-3xl">{t.landing.categoriesTitle}</h2>
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {CATEGORIES.map((c) => {
              const k = knowledge.categories[c];
              return (
                <Link key={c} href={`/guide#${c}`} className="group rounded-lg border bg-card p-5 transition-shadow hover:shadow-md">
                  <CategoryIcon category={c} boxed />
                  <h3 className="mt-3 font-semibold group-hover:text-primary">{t.categories[c]}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{pick(k.short)}</p>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-4 py-16 md:grid-cols-2">
        <Card>
          <CardContent className="pt-5">
            <h2 className="flex items-center gap-2 text-xl font-bold"><ShieldCheck className="h-5 w-5 text-primary" />{t.landing.honestTitle}</h2>
            <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
              {t.landing.honest.map((h) => <li key={h} className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />{h}</li>)}
            </ul>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5">
            <h2 className="flex items-center gap-2 text-xl font-bold"><AlertTriangle className="h-5 w-5 text-warning" />{t.landing.limitsTitle}</h2>
            <p className="mt-4 text-sm text-muted-foreground">{t.landing.limits}</p>
          </CardContent>
        </Card>
      </section>
    </>
  );
}
