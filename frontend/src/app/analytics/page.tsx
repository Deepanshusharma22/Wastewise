"use client";

import { useCallback, useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Gauge, ScanLine, ShieldAlert, Trophy } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { categoryColor } from "@/components/category-icon";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import type { AnalyticsSummary, Category } from "@/lib/types";
import { pct } from "@/lib/utils";

function Kpi({ label, value, icon: Icon }: { label: string; value: string; icon: React.ElementType }) {
  return (
    <Card>
      <CardContent className="pt-5">
        <Icon className="h-5 w-5 text-primary" aria-hidden />
        <p className="mt-3 text-2xl font-bold tabular-nums">{value}</p>
        <p className="text-sm text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );
}

export default function AnalyticsPage() {
  const { t, lang } = useI18n();
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setError(null);
    try { setData(await api.analytics()); } catch (e) { setError(e); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const catName = (c: string) => t.categories[c as Category] ?? c;
  const daily = data?.daily_counts.map((d) => ({
    ...d,
    label: new Intl.DateTimeFormat(lang === "hi" ? "hi-IN" : "en-IN", { day: "numeric", month: "short" }).format(new Date(`${d.date}T00:00:00Z`)),
  }));

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <PageHeader title={t.analytics.title} sub={t.analytics.sub} />
      {error ? <ErrorState error={error} onRetry={load} /> : !data ? (
        <div className="grid gap-4 md:grid-cols-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-32" />)}</div>
      ) : data.total_scans === 0 ? (
        <p className="rounded-lg border border-dashed p-10 text-center text-muted-foreground">{t.analytics.empty}</p>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi label={t.dashboard.total} value={String(data.total_scans)} icon={ScanLine} />
            <Kpi label={t.analytics.avgConf} value={pct(data.average_confidence, 1)} icon={Gauge} />
            <Kpi label={t.analytics.top} value={data.most_common_category ? catName(data.most_common_category) : "-"} icon={Trophy} />
            <Kpi label={t.analytics.hazard} value={String(data.hazardous_or_ewaste_scans)} icon={ShieldAlert} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle>{t.analytics.distribution}</CardTitle></CardHeader>
              <CardContent>
                <div className="h-64" role="img" aria-label={t.analytics.distribution}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={data.category_distribution} dataKey="count" nameKey="category" innerRadius={55} outerRadius={95} paddingAngle={2} isAnimationActive={false}>
                        {data.category_distribution.map((d) => <Cell key={d.category} fill={categoryColor(d.category)} />)}
                      </Pie>
                      <Tooltip formatter={(v, _n, item) => [`${v} (${(item?.payload as { percentage: number }).percentage.toFixed(1)}%)`, catName(String((item?.payload as { category: string }).category))]} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <ul className="mt-4 grid grid-cols-2 gap-2 text-sm">
                  {data.category_distribution.map((d) => (
                    <li key={d.category} className="flex items-center gap-2">
                      <span className="h-3 w-3 rounded-sm" style={{ backgroundColor: categoryColor(d.category) }} aria-hidden />
                      <span className="flex-1">{catName(d.category)}</span>
                      <span className="tabular-nums text-muted-foreground">{d.count} · {d.percentage.toFixed(0)}%</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>{t.analytics.daily}</CardTitle></CardHeader>
              <CardContent>
                <div className="h-72" role="img" aria-label={t.analytics.daily}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={daily} margin={{ left: -20, right: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                      <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} interval={4} />
                      <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
                      <Tooltip cursor={{ fill: "var(--accent)" }} contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8 }} />
                      <Bar dataKey="count" fill="var(--primary)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <p className="mt-3 text-sm text-muted-foreground">
                  {t.analytics.confidentShare}: <span className="font-medium text-foreground">{pct(data.confident_scans / data.total_scans)}</span>
                </p>
              </CardContent>
            </Card>
          </div>
          {data.truncated && <p className="text-xs text-muted-foreground">{t.analytics.truncated}</p>}
        </div>
      )}
    </div>
  );
}
