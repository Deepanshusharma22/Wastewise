"use client";

import { useI18n } from "@/lib/i18n/provider";
import { pct } from "@/lib/utils";
import { categoryColor } from "@/components/category-icon";
import type { CategoryProbability } from "@/lib/types";

export function ConfidenceRing({ value, confident, color }: { value: number; confident: boolean; color: string }) {
  const r = 42;
  const c = 2 * Math.PI * r;
  const stroke = confident ? color : "var(--warning)";
  return (
    <div className="relative h-28 w-28 shrink-0" role="img" aria-label={`${pct(value)}`}>
      <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
        <circle cx="50" cy="50" r={r} fill="none" stroke="var(--muted)" strokeWidth="9" />
        <circle cx="50" cy="50" r={r} fill="none" stroke={stroke} strokeWidth="9" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - value)} className="transition-[stroke-dashoffset] duration-700" />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-2xl font-bold tabular-nums">{pct(value)}</span>
    </div>
  );
}

export function TopPredictions({ items }: { items: CategoryProbability[] }) {
  const { t } = useI18n();
  return (
    <ul className="space-y-3" aria-label={t.result.top3}>
      {items.map((p, i) => (
        <li key={p.category}>
          <div className="mb-1 flex justify-between text-sm">
            <span className={i === 0 ? "font-semibold" : "text-muted-foreground"}>{t.categories[p.category]}</span>
            <span className="tabular-nums text-muted-foreground">{pct(p.probability, 1)}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${Math.max(1, p.probability * 100)}%`, backgroundColor: categoryColor(p.category) }} />
          </div>
        </li>
      ))}
    </ul>
  );
}
