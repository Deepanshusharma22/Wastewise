"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, CheckCircle2, ImagePlus, Loader2, Lock, ScanLine, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/page-header";
import { useAuth } from "@/components/auth-provider";
import { useErrorMessage } from "@/components/error-state";
import { stashGradcam } from "@/components/result/view-model";
import { api } from "@/lib/api";
import { prepareUpload } from "@/lib/image";
import { useI18n } from "@/lib/i18n/provider";
import { checkFile } from "@/lib/validation";
import { cn } from "@/lib/utils";

/* eslint-disable @next/next/no-img-element -- local object URL preview */
export default function AnalyzePage() {
  const { t } = useI18n();
  const { profile } = useAuth();
  const router = useRouter();
  const errMsg = useErrorMessage();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const cameraInput = useRef<HTMLInputElement>(null);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const accept = useCallback((f: File | undefined | null) => {
    if (!f) return;
    // Large files are fine here: they're downscaled before upload. Only reject wrong types / absurd sizes.
    const p = checkFile({ type: f.type, size: Math.min(f.size, 1) });
    if (p === "badType") { setProblem(t.analyze.badType); return; }
    if (f.size > 25 * 1024 * 1024) { setProblem(t.analyze.tooLarge); return; }
    setProblem(null);
    setFile(f);
    setPreview(URL.createObjectURL(f));
  }, [t]);

  async function analyze() {
    if (!file) return;
    setBusy(true);
    try {
      const upload = await prepareUpload(file);
      if (checkFile(upload) === "tooLarge") { setProblem(t.analyze.tooLarge); return; }
      const result = await api.predict(upload);
      stashGradcam(result.id, result.gradcam_image);
      try { sessionStorage.setItem(`ww-result-${result.id}`, JSON.stringify({ ...result, gradcam_image: null })); } catch { /* ignore */ }
      router.push(`/result/${result.id}`);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  function clear() {
    setFile(null);
    setPreview(null);
    setProblem(null);
    if (fileInput.current) fileInput.current.value = "";
    if (cameraInput.current) cameraInput.current.value = "";
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <PageHeader title={t.analyze.title} sub={t.analyze.sub} />
      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardContent className="pt-5">
            <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={(e) => accept(e.target.files?.[0])} aria-label={t.analyze.browse} />
            <input ref={cameraInput} type="file" accept="image/*" capture="environment" className="sr-only" onChange={(e) => accept(e.target.files?.[0])} aria-label={t.analyze.camera} />
            {!preview ? (
              <div
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => { e.preventDefault(); setDragging(false); accept(e.dataTransfer.files?.[0]); }}
                className={cn("flex aspect-[4/3] flex-col items-center justify-center gap-4 rounded-lg border-2 border-dashed p-6 text-center transition-colors",
                  dragging ? "border-primary bg-accent" : "border-input")}
              >
                <span className="flex h-14 w-14 items-center justify-center rounded-full bg-accent text-accent-foreground"><ImagePlus className="h-7 w-7" aria-hidden /></span>
                <p className="font-medium">{t.analyze.drop}</p>
                <p className="text-sm text-muted-foreground">{t.analyze.or}</p>
                <div className="flex flex-wrap justify-center gap-2">
                  <Button onClick={() => fileInput.current?.click()}><ImagePlus />{t.analyze.browse}</Button>
                  <Button variant="outline" onClick={() => cameraInput.current?.click()}><Camera />{t.analyze.camera}</Button>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="relative overflow-hidden rounded-lg border bg-muted">
                  <img src={preview} alt="" className="mx-auto max-h-[28rem] w-full object-contain" />
                  {busy && (
                    <div className="absolute inset-0 overflow-hidden bg-forest/30" aria-hidden>
                      <div className="animate-scan h-1/3 w-full bg-gradient-to-b from-transparent via-lime/50 to-transparent" />
                    </div>
                  )}
                  {!busy && (
                    <Button variant="outline" size="icon" className="absolute right-2 top-2" onClick={clear} aria-label={t.analyze.remove}><X /></Button>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button size="lg" onClick={analyze} disabled={busy} className="flex-1">
                    {busy ? <Loader2 className="animate-spin" /> : <ScanLine />}{busy ? t.analyze.analyzing : t.analyze.analyze}
                  </Button>
                  <Button size="lg" variant="outline" onClick={() => fileInput.current?.click()} disabled={busy}>{t.analyze.change}</Button>
                </div>
              </div>
            )}
            {problem && <p role="alert" className="mt-3 text-sm text-destructive">{problem}</p>}
            <p className="mt-4 flex items-start gap-2 text-xs text-muted-foreground">
              <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              {profile && !profile.save_images ? t.analyze.privacyOff : t.analyze.privacy}
            </p>
          </CardContent>
        </Card>
        <Card className="h-fit">
          <CardHeader><CardTitle>{t.analyze.tipsTitle}</CardTitle></CardHeader>
          <CardContent>
            <ul className="space-y-3 text-sm">
              {t.analyze.tips.map((tip) => <li key={tip} className="flex gap-2"><CheckCircle2 className="h-4 w-4 shrink-0 text-primary" aria-hidden />{tip}</li>)}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
