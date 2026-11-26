"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, FilterX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, NativeSelect } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { HistoryCard } from "@/components/history-card";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { CATEGORIES, type HistoryPage } from "@/lib/types";

const PAGE_SIZE = 12;
const EMPTY = { category: "", confident: "", sort: "newest", date_from: "", date_to: "" };

export default function HistoryPageView() {
  const { t } = useI18n();
  const [filters, setFilters] = useState(EMPTY);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<HistoryPage | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.history({ page, page_size: PAGE_SIZE, ...filters }));
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, [page, filters]);

  useEffect(() => { void load(); }, [load]);

  const set = (k: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setPage(1);
    setFilters((f) => ({ ...f, [k]: e.target.value }));
  };
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const filtered = JSON.stringify(filters) !== JSON.stringify(EMPTY);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <PageHeader title={t.history.title} sub={t.history.sub} />
      <div className="mb-6 grid gap-3 rounded-lg border bg-card p-4 sm:grid-cols-2 lg:grid-cols-6">
        <div className="space-y-1.5 lg:col-span-2">
          <Label htmlFor="f-cat">{t.history.category}</Label>
          <NativeSelect id="f-cat" value={filters.category} onChange={set("category")}>
            <option value="">{t.history.all}</option>
            {CATEGORIES.map((c) => <option key={c} value={c}>{t.categories[c]}</option>)}
          </NativeSelect>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="f-conf">{t.result.confidence}</Label>
          <NativeSelect id="f-conf" value={filters.confident} onChange={set("confident")}>
            <option value="">{t.history.any}</option>
            <option value="true">{t.history.confident}</option>
            <option value="false">{t.history.uncertain}</option>
          </NativeSelect>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="f-from">{t.history.from}</Label>
          <Input id="f-from" type="date" value={filters.date_from} max={filters.date_to || undefined} onChange={set("date_from")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="f-to">{t.history.to}</Label>
          <Input id="f-to" type="date" value={filters.date_to} min={filters.date_from || undefined} onChange={set("date_to")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="f-sort">{t.history.sort}</Label>
          <NativeSelect id="f-sort" value={filters.sort} onChange={set("sort")}>
            <option value="newest">{t.history.newest}</option>
            <option value="oldest">{t.history.oldest}</option>
            <option value="confidence_desc">{t.history.highest}</option>
            <option value="confidence_asc">{t.history.lowest}</option>
          </NativeSelect>
        </div>
        {filtered && (
          <div className="lg:col-span-6">
            <Button variant="ghost" size="sm" onClick={() => { setFilters(EMPTY); setPage(1); }}><FilterX />{t.history.clear}</Button>
          </div>
        )}
      </div>

      {error ? <ErrorState error={error} onRetry={load} /> : loading && !data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="aspect-[4/4]" />)}</div>
      ) : data && data.items.length === 0 ? (
        <p className="rounded-lg border border-dashed p-10 text-center text-muted-foreground">{t.history.empty}</p>
      ) : data && (
        <>
          <div className={`grid gap-4 sm:grid-cols-2 lg:grid-cols-4 ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
            {data.items.map((it) => <HistoryCard key={it.id} item={it} />)}
          </div>
          <nav className="mt-8 flex items-center justify-center gap-3" aria-label="Pagination">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}><ChevronLeft />{t.history.prev}</Button>
            <span className="text-sm text-muted-foreground">{t.history.page} {page} {t.history.of} {pages}</span>
            <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>{t.history.next}<ChevronRight /></Button>
          </nav>
        </>
      )}
    </div>
  );
}
