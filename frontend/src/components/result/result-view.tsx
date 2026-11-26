"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Clock, Cpu, ScanLine, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { CategoryIcon, categoryColor } from "@/components/category-icon";
import { useErrorMessage } from "@/components/error-state";
import { ConfidenceRing, TopPredictions } from "./confidence-meter";
import { FeedbackForm } from "./feedback-form";
import { GradcamViewer } from "./gradcam-viewer";
import { GuidancePanel, UncertainBanner } from "./guidance-panel";
import { NoticeList, QualityWarnings } from "./notices";
import type { ResultVM } from "./view-model";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { formatDate, pct } from "@/lib/utils";

export function ResultView({ r }: { r: ResultVM }) {
  const { t, lang, pick } = useI18n();
  const router = useRouter();
  const errMsg = useErrorMessage();
  const [confirm, setConfirm] = useState(false);
  const color = categoryColor(r.category);

  async function remove() {
    try {
      await api.deleteHistory(r.id);
      toast.success(t.result.deleted);
      router.push("/history");
    } catch (e) {
      toast.error(errMsg(e));
    }
  }

  return (
    <div className="space-y-6 animate-fade-up">
      {!r.isConfident && <UncertainBanner reasons={r.reasons} />}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <Card>
          <CardContent className="pt-5"><GradcamViewer imageUrl={r.imageUrl} gradcam={r.gradcam} /></CardContent>
        </Card>

        <div className="space-y-6">
          <Card style={{ borderTop: `4px solid ${r.isConfident ? color : "var(--warning)"}` }}>
            <CardContent className="flex flex-wrap items-center gap-5 pt-5">
              <ConfidenceRing value={r.confidence} confident={r.isConfident} color={color} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <CategoryIcon category={r.category} boxed className="h-9 w-9" />
                  <h2 className="text-2xl font-bold" aria-live="polite">
                    {r.isConfident ? t.categories[r.category] : `${t.categories[r.category]}?`}
                  </h2>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{t.result.confidence}: <span className="font-medium tabular-nums">{pct(r.confidence, 1)}</span></p>
                {r.itemLabel && r.isConfident && (
                  <p className="mt-2 text-sm">
                    {t.result.item}: <Badge variant="lime">{pick(r.itemLabel)}{r.itemConfidence != null && ` · ${pct(r.itemConfidence)}`}</Badge>
                  </p>
                )}
                <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1"><Clock className="h-3.5 w-3.5" />{formatDate(r.createdAt, lang)}</span>
                  <span className="inline-flex items-center gap-1"><Cpu className="h-3.5 w-3.5" />{t.result.model}: {r.modelVersion}</span>
                  {r.inferenceMs != null && <span>{t.result.time}: {Math.round(r.inferenceMs)} ms</span>}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>{t.result.top3}</CardTitle></CardHeader>
            <CardContent><TopPredictions items={r.top} /></CardContent>
          </Card>

          <NoticeList notices={r.notices} />
          <QualityWarnings warnings={r.quality} />
        </div>
      </div>

      <GuidancePanel g={r.guidance} />
      <FeedbackForm predictionId={r.id} initial={r.feedback} />

      <div className="flex flex-wrap justify-between gap-3">
        <Button asChild size="lg"><Link href="/analyze"><ScanLine />{t.result.analyzeAnother}</Link></Button>
        <Button variant="outline" onClick={() => setConfirm(true)}><Trash2 />{t.result.delete}</Button>
      </div>

      <Dialog open={confirm} onOpenChange={setConfirm}>
        <DialogContent>
          <DialogTitle>{t.result.delete}</DialogTitle>
          <DialogDescription>{t.result.confirmDelete}</DialogDescription>
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setConfirm(false)}>{t.common.cancel}</Button>
            <Button variant="destructive" onClick={remove}>{t.result.delete}</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
