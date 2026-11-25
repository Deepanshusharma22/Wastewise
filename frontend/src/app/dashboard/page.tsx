"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, CalendarDays, Lightbulb, Recycle, ScanLine } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/components/auth-provider";
import { ErrorState } from "@/components/error-state";
import { HistoryCard } from "@/components/history-card";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { knowledge } from "@/lib/knowledge";
import { CATEGORIES, type AnalyticsSummary, type HistoryItem } from "@/lib/types";

function Stat({ label, value, icon: Icon }: { label: string; value: string | number; icon: React.ElementType }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 pt-5">
        <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-accent text-accent-foreground"><Icon className="h-5 w-5" aria-hidden /></span>
        <div>
          <p className="text-2xl font-bold tabular-nums">{value}</p>
          <p className="text-sm text-muted-foreground">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const { t, pick } = useI18n();
  const { profile, user } = useAuth();
  const [stats, setStats] = useState<AnalyticsSummary | null>(null);
  const [recent, setRecent] = useState<HistoryItem[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, h] = await Promise.all([api.analytics(), api.history({ page: 1, page_size: 4 })]);
      setStats(s);
      setRecent(h.items);
    } catch (e) {
      setError(e);
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  // deterministic "tip of the day" from the knowledge base
  const tip = useMemo(() => {
    const day = Math.floor(Date.now() / 86_400_000);
    const c = CATEGORIES[day % CATEGORIES.length];
    const list = pick(knowledge.categories[c].common_mistakes) as string[];
    return { c, text: list[day % Math.max(1, list.length)] };
  }, [pick]);

  const name = profile?.full_name?.split(" ")[0] || user?.email?.split("@")[0] || "";

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight md:text-3xl">{t.dashboard.greeting}{name && `, ${name}`} 👋</h1>
          <p className="mt-1 text-muted-foreground">{t.dashboard.sub}</p>
        </div>
        <Button asChild size="lg"><Link href="/analyze"><ScanLine />{t.dashboard.newScan}</Link></Button>
      </div>

      {error ? <ErrorState error={error} onRetry={load} /> : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {stats ? (
              <>
                <Stat label={t.dashboard.total} value={stats.total_scans} icon={ScanLine} />
                <Stat label={t.dashboard.recyclable} value={stats.recyclable_scans} icon={Recycle} />
                <Stat label={t.dashboard.uncertain} value={stats.uncertain_scans} icon={AlertTriangle} />
                <Stat label={t.dashboard.last7} value={stats.scans_last_7_days} icon={CalendarDays} />
              </>
            ) : Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
          </div>

          <div className="mt-8 grid gap-6 lg:grid-cols-[2fr_1fr]">
            <section>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-lg font-semibold">{t.dashboard.recent}</h2>
                <Link href="/history" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">{t.dashboard.viewAll}<ArrowRight className="h-4 w-4" /></Link>
              </div>
              {recent === null ? (
                <div className="grid gap-4 sm:grid-cols-2">{Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-56" />)}</div>
              ) : recent.length === 0 ? (
                <div className="rounded-lg border border-dashed p-10 text-center">
                  <p className="text-muted-foreground">{t.dashboard.empty}</p>
                  <Button asChild className="mt-4"><Link href="/analyze"><ScanLine />{t.nav.analyze}</Link></Button>
                </div>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">{recent.map((it) => <HistoryCard key={it.id} item={it} />)}</div>
              )}
            </section>
            <Card className="h-fit border-lime/60 bg-lime/15">
              <CardHeader><CardTitle className="flex items-center gap-2"><Lightbulb className="h-5 w-5 text-primary" />{t.dashboard.tip}</CardTitle></CardHeader>
              <CardContent>
                <p className="text-sm font-medium">{t.categories[tip.c]}</p>
                <p className="mt-1 text-sm text-muted-foreground">{tip.text}</p>
                <Link href={`/guide#${tip.c}`} className="mt-3 inline-flex items-center gap-1 text-sm text-primary hover:underline">{t.nav.guide}<ArrowRight className="h-4 w-4" /></Link>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
