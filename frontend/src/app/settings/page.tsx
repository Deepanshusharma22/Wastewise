"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Camera, Cpu, Loader2, Trash2, UserRound } from "lucide-react";
import { useTheme } from "next-themes";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input, NativeSelect } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { PageHeader } from "@/components/page-header";
import { useAuth } from "@/components/auth-provider";
import { useErrorMessage } from "@/components/error-state";
import { api } from "@/lib/api";
import { getSupabase } from "@/lib/supabase/client";
import { useI18n } from "@/lib/i18n/provider";
import type { Lang, ModelInfo } from "@/lib/types";
import { pct } from "@/lib/utils";

/* eslint-disable @next/next/no-img-element -- signed avatar URL */
export default function SettingsPage() {
  const { t, lang, setLang } = useI18n();
  const { setTheme } = useTheme();
  const { user, profile, refreshProfile } = useAuth();
  const router = useRouter();
  const errMsg = useErrorMessage();
  const [name, setName] = useState("");
  const [prefLang, setPrefLang] = useState<Lang>(lang);
  const [theme, setThemePref] = useState<"light" | "dark" | "system">("system");
  const [saveImages, setSaveImages] = useState(true);
  const [avatar, setAvatar] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [model, setModel] = useState<ModelInfo | null>(null);
  const [delOpen, setDelOpen] = useState(false);
  const [delText, setDelText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!profile) return;
    setName(profile.full_name ?? "");
    setPrefLang(profile.preferred_language);
    setThemePref(profile.theme);
    setSaveImages(profile.save_images);
    if (profile.avatar_url) {
      getSupabase().storage.from("avatars").createSignedUrl(profile.avatar_url, 3600)
        .then(({ data }) => setAvatar(data?.signedUrl ?? null));
    }
  }, [profile]);

  useEffect(() => { api.modelInfo().then(setModel).catch(() => setModel(null)); }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!user) return;
    setSaving(true);
    const { error } = await getSupabase().from("profiles")
      .update({ full_name: name.trim() || null, preferred_language: prefLang, theme, save_images: saveImages })
      .eq("id", user.id);
    setSaving(false);
    if (error) { toast.error(error.message); return; }
    setLang(prefLang);
    setTheme(theme);
    await refreshProfile();
    toast.success(t.settings.saved);
  }

  async function uploadAvatar(f: File | undefined) {
    if (!f || !user) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(f.type) || f.size > 2 * 1024 * 1024) {
      toast.error(f.size > 2 * 1024 * 1024 ? "Max 2 MB" : t.analyze.badType);
      return;
    }
    setUploading(true);
    const ext = f.type === "image/png" ? "png" : f.type === "image/webp" ? "webp" : "jpg";
    const path = `${user.id}/avatar.${ext}`;
    const sb = getSupabase();
    const { error } = await sb.storage.from("avatars").upload(path, f, { upsert: true, contentType: f.type, cacheControl: "3600" });
    if (!error) {
      await sb.from("profiles").update({ avatar_url: path }).eq("id", user.id);
      const { data } = await sb.storage.from("avatars").createSignedUrl(path, 3600);
      setAvatar(data?.signedUrl ? `${data.signedUrl}&v=${Date.now()}` : null);
      await refreshProfile();
    } else {
      toast.error(error.message);
    }
    setUploading(false);
  }

  async function deleteAccount() {
    setDeleting(true);
    try {
      await api.deleteAccount();
      await getSupabase().auth.signOut();
      toast.success(t.settings.deleted);
      router.replace("/");
      router.refresh();
    } catch (e) {
      toast.error(errMsg(e));
      setDeleting(false);
    }
  }

  const m = (model?.metrics ?? null) as Record<string, number> | null;

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <PageHeader title={t.settings.title} />
      <form onSubmit={save} className="space-y-6">
        <Card>
          <CardHeader><CardTitle>{t.settings.profile}</CardTitle></CardHeader>
          <CardContent className="space-y-5">
            <div className="flex items-center gap-4">
              <div className="flex h-20 w-20 items-center justify-center overflow-hidden rounded-full border bg-muted">
                {avatar ? <img src={avatar} alt={t.settings.avatar} className="h-full w-full object-cover" /> : <UserRound className="h-9 w-9 text-muted-foreground" aria-hidden />}
              </div>
              <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={(e) => uploadAvatar(e.target.files?.[0])} aria-label={t.settings.upload} />
              <Button type="button" variant="outline" onClick={() => fileRef.current?.click()} disabled={uploading}>
                {uploading ? <Loader2 className="animate-spin" /> : <Camera />}{t.settings.upload}
              </Button>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="name">{t.auth.fullName}</Label>
                <Input id="name" maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="email">{t.auth.email}</Label>
                <Input id="email" value={user?.email ?? ""} disabled />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>{t.settings.prefs}</CardTitle></CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="lang">{t.settings.language}</Label>
              <NativeSelect id="lang" value={prefLang} onChange={(e) => setPrefLang(e.target.value as Lang)}>
                <option value="en">English</option>
                <option value="hi">हिन्दी</option>
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="theme">{t.settings.theme}</Label>
              <NativeSelect id="theme" value={theme} onChange={(e) => setThemePref(e.target.value as typeof theme)}>
                <option value="system">{t.settings.system}</option>
                <option value="light">{t.settings.light}</option>
                <option value="dark">{t.settings.dark}</option>
              </NativeSelect>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>{t.settings.privacy}</CardTitle></CardHeader>
          <CardContent>
            <div className="flex items-start justify-between gap-4">
              <div>
                <Label htmlFor="save-images">{t.settings.saveImages}</Label>
                <p className="mt-1 text-sm text-muted-foreground">{t.settings.saveImagesHelp}</p>
              </div>
              <Switch id="save-images" checked={saveImages} onCheckedChange={setSaveImages} />
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button type="submit" disabled={saving}>{saving && <Loader2 className="animate-spin" />}{t.settings.save}</Button>
        </div>
      </form>

      {model && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Cpu className="h-5 w-5 text-primary" />{t.settings.modelTitle}</CardTitle>
            <CardDescription>{model.model_name} · v{model.model_version} · {model.architecture}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {m && (
              <>
                <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {([
                    [t.settings.mAcc, pct(m.test_accuracy, 1)],
                    [t.settings.mF1, pct(m.test_f1_macro, 1)],
                    [t.settings.mCoverage, pct(m.test_coverage_at_threshold, 1)],
                    [t.settings.mOod, pct(m.ood_rejection_rate, 1)],
                  ] as const).map(([k, v]) => (
                    <div key={k} className="rounded-md border p-3">
                      <dt className="text-xs text-muted-foreground">{k}</dt>
                      <dd className="text-lg font-semibold tabular-nums">{v}</dd>
                    </div>
                  ))}
                </dl>
                <p className="text-xs text-muted-foreground">
                  {t.settings.mNote.replace("{n}", String(m.test_images ?? "-")).replace("{th}", pct(model.confidence_threshold))}
                </p>
              </>
            )}
            {model.limitations.length > 0 && (
              <ul className="list-disc space-y-1 pl-4 text-muted-foreground">{model.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
            )}
          </CardContent>
        </Card>
      )}

      <Card className="mt-6 border-destructive/40">
        <CardHeader>
          <CardTitle className="text-destructive">{t.settings.danger}</CardTitle>
          <CardDescription>{t.settings.deleteHelp}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="destructive" onClick={() => setDelOpen(true)}><Trash2 />{t.settings.deleteAccount}</Button>
        </CardContent>
      </Card>

      <Dialog open={delOpen} onOpenChange={(o) => { setDelOpen(o); setDelText(""); }}>
        <DialogContent>
          <DialogTitle>{t.settings.deleteAccount}</DialogTitle>
          <DialogDescription>{t.settings.deleteHelp}</DialogDescription>
          <div className="mt-4 space-y-1.5">
            <Label htmlFor="del-confirm">{t.settings.deleteConfirm}</Label>
            <Input id="del-confirm" value={delText} onChange={(e) => setDelText(e.target.value)} autoComplete="off" />
          </div>
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDelOpen(false)}>{t.common.cancel}</Button>
            <Button variant="destructive" disabled={delText !== "DELETE" || deleting} onClick={deleteAccount}>
              {deleting && <Loader2 className="animate-spin" />}{t.settings.deleteAccount}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
