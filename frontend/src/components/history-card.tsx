"use client";

import Link from "next/link";
import { AlertTriangle, ImageOff } from "lucide-react";
import { CategoryIcon, categoryColor } from "@/components/category-icon";
import { useI18n } from "@/lib/i18n/provider";
import { itemLabel } from "@/lib/knowledge";
import type { HistoryItem } from "@/lib/types";
import { formatDate, pct } from "@/lib/utils";

/* eslint-disable @next/next/no-img-element -- short-lived signed URLs */
export function HistoryCard({ item }: { item: HistoryItem }) {
  const { t, lang, pick } = useI18n();
  const label = itemLabel(item.predicted_item);
  return (
    <Link href={`/result/${item.id}`} className="group overflow-hidden rounded-lg border bg-card shadow-sm transition-shadow hover:shadow-md focus-visible:ring-2 focus-visible:ring-ring">
      <div className="relative aspect-[4/3] bg-muted">
        {item.image_url ? (
          <img src={item.image_url} alt="" loading="lazy" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground"><ImageOff className="h-8 w-8" aria-hidden /></div>
        )}
        <span className="absolute left-2 top-2 rounded-full px-2 py-0.5 text-xs font-semibold text-white" style={{ backgroundColor: item.is_confident ? categoryColor(item.predicted_category) : "#b45309" }}>
          {pct(item.confidence)}
        </span>
      </div>
      <div className="flex items-start gap-3 p-3">
        <CategoryIcon category={item.predicted_category} boxed className="h-9 w-9 shrink-0" />
        <div className="min-w-0">
          <p className="flex items-center gap-1 truncate font-medium group-hover:text-primary">
            {t.categories[item.predicted_category]}
            {!item.is_confident && <AlertTriangle className="h-3.5 w-3.5 text-warning" aria-label={t.history.uncertain} />}
          </p>
          <p className="truncate text-xs text-muted-foreground">{label && item.is_confident ? `${pick(label)} · ` : ""}{formatDate(item.created_at, lang)}</p>
        </div>
      </div>
    </Link>
  );
}
