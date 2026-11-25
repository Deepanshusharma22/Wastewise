"use client";

import { useState } from "react";
import { Check, ThumbsDown, ThumbsUp } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NativeSelect, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useErrorMessage } from "@/components/error-state";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { CATEGORIES, type Feedback } from "@/lib/types";

export function FeedbackForm({ predictionId, initial }: { predictionId: string; initial: Feedback | null }) {
  const { t } = useI18n();
  const errMsg = useErrorMessage();
  const [correct, setCorrect] = useState<boolean | null>(initial?.user_correctness_feedback ?? null);
  const [corrected, setCorrected] = useState<string>(initial?.corrected_category ?? "");
  const [comments, setComments] = useState(initial?.comments ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(Boolean(initial));

  async function submit(value: boolean) {
    setSaving(true);
    try {
      await api.feedback(predictionId, {
        user_correctness_feedback: value,
        corrected_category: value ? null : corrected || null,
        comments: comments.trim() || null,
      });
      setSaved(true);
      toast.success(t.result.thanks);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader><CardTitle>{t.result.feedbackTitle}</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2" role="group" aria-label={t.result.feedbackTitle}>
          <Button variant={correct === true ? "default" : "outline"} aria-pressed={correct === true} disabled={saving}
            onClick={() => { setCorrect(true); void submit(true); }}>
            <ThumbsUp />{t.result.yes}
          </Button>
          <Button variant={correct === false ? "destructive" : "outline"} aria-pressed={correct === false} disabled={saving}
            onClick={() => { setCorrect(false); setSaved(false); }}>
            <ThumbsDown />{t.result.no}
          </Button>
          {saved && <span className="ml-auto inline-flex items-center gap-1 text-sm text-primary"><Check className="h-4 w-4" />{t.result.thanks}</span>}
        </div>
        {correct === false && (
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); void submit(false); }}>
            <div className="space-y-1.5">
              <Label htmlFor="fb-cat">{t.result.correctCategory}</Label>
              <NativeSelect id="fb-cat" value={corrected} onChange={(e) => setCorrected(e.target.value)}>
                <option value="">-</option>
                {CATEGORIES.map((c) => <option key={c} value={c}>{t.categories[c]}</option>)}
                <option value="other">{t.result.other}</option>
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="fb-comments">{t.result.comments}</Label>
              <Textarea id="fb-comments" maxLength={1000} value={comments} onChange={(e) => setComments(e.target.value)} />
            </div>
            <Button type="submit" disabled={saving}>{t.result.submit}</Button>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
