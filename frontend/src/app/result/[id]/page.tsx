"use client";

import { use, useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { ResultView } from "@/components/result/result-view";
import { fromDetail, fromPrediction, readGradcam, type ResultVM } from "@/components/result/view-model";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import type { PredictionResult } from "@/lib/types";

export default function ResultPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t } = useI18n();
  const [vm, setVm] = useState<ResultVM | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setError(null);
    const fresh = sessionStorage.getItem(`ww-result-${id}`);
    if (fresh) {
      try {
        const p = JSON.parse(fresh) as PredictionResult;
        setVm({ ...fromPrediction(p), gradcam: readGradcam(id) });
        return;
      } catch { /* fall through to the API */ }
    }
    try {
      const d = await api.historyDetail(id);
      setVm(fromDetail(d, readGradcam(id)));
    } catch (e) {
      setError(e);
    }
  }, [id]);

  useEffect(() => { void load(); }, [load]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <PageHeader title={t.result.title} />
      {error ? <ErrorState error={error} onRetry={load} /> : vm ? <ResultView r={vm} /> : (
        <div className="grid gap-6 lg:grid-cols-2" aria-busy="true" aria-label={t.common.loading}>
          <Skeleton className="aspect-square" />
          <div className="space-y-4"><Skeleton className="h-36" /><Skeleton className="h-40" /><Skeleton className="h-20" /></div>
        </div>
      )}
    </div>
  );
}
