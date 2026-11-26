"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AlertTriangle, Loader2, MailCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthCard, FormError } from "../auth-card";
import { backend } from "@/lib/backend";
import { useI18n } from "@/lib/i18n/provider";

function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
}

function LoginForm() {
  const { t } = useI18n();
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(params.get("error"));
  const [busy, setBusy] = useState(false);
  const [linkSent, setLinkSent] = useState(false);
  const [newLink, setNewLink] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [showCode, setShowCode] = useState(false);

  // A link that could not be used lands here with ?error=… — offer a way out.
  const linkProblem = Boolean(params.get("error"));

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const b = await backend();
      const { user, error: err } = await b.login(email, password);
      if (err) {
        const needsConfirm = /confirm|not confirmed/i.test(err.message);
        setError(needsConfirm ? t.auth.emailNotConfirmed : err.message);
        return;
      }
      if (user) {
        router.replace(safeNext(params.get("next")));
        router.refresh();
      }
    } finally {
      setBusy(false);
    }
  }

  async function sendNewLink() {
    setBusy(true);
    setError(null);
    const b = await backend();
    const r = await b.resendConfirmation(email.trim(), b.callbackUrl("/dashboard"));
    setBusy(false);
    if (r.alreadyConfirmed) { setError(t.auth.alreadyConfirmed); return; }
    setLinkSent(r.ok);
    setNewLink(r.emailLink);
  }

  async function verifyCode(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const b = await backend();
    const r = await b.verifyCode(email, code, "signup");
    setBusy(false);
    if (r.error) { setError(r.error.message); return; }
    if (r.user) { router.replace(safeNext(params.get("next"))); router.refresh(); }
  }

  return (
    <AuthCard title={t.auth.loginTitle} sub={t.auth.loginSub}
      footer={<>{t.auth.noAccount} <Link className="font-medium text-primary hover:underline" href="/signup">{t.auth.signup}</Link></>}>
      {linkProblem && (
        <div className="mb-4 space-y-3 rounded-md border border-warning/40 bg-warning/10 p-3">
          <p className="flex items-center gap-2 text-sm font-semibold text-warning">
            <AlertTriangle className="h-4 w-4" aria-hidden />{t.auth.linkProblemTitle}
          </p>
          <p className="text-xs text-muted-foreground">{t.auth.linkFixHint}</p>
          <div className="space-y-1.5">
            <Label htmlFor="new-link-email">{t.auth.emailForNewLink}</Label>
            <Input id="new-link-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <Button type="button" variant="outline" className="w-full" onClick={sendNewLink} disabled={busy || !email}>
            {busy ? <Loader2 className="animate-spin" /> : <MailCheck />}{t.auth.sendNewLink}
          </Button>
          {linkSent && <p role="status" className="text-xs text-primary">{t.auth.resent}</p>}
          {newLink && (
            <Button asChild className="w-full"><a href={newLink}>{t.auth.openLink}</a></Button>
          )}
        </div>
      )}

      <form className="space-y-4" onSubmit={onSubmit} noValidate>
        <FormError message={error} />
        <div className="space-y-1.5">
          <Label htmlFor="email">{t.auth.email}</Label>
          <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">{t.auth.password}</Label>
            <Link href="/forgot-password" className="text-xs text-primary hover:underline">{t.auth.forgot}</Link>
          </div>
          <Input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <Button type="submit" className="w-full" disabled={busy || !email || !password}>
          {busy && <Loader2 className="animate-spin" />}{t.auth.login}
        </Button>
      </form>

      <div className="mt-4 space-y-3 border-t pt-4 text-sm">
        {!showCode ? (
          <button type="button" className="text-xs text-primary hover:underline" onClick={() => setShowCode(true)}>
            {t.auth.useCodeInstead}
          </button>
        ) : (
          <form className="space-y-2" onSubmit={verifyCode}>
            <Label htmlFor="otp">{t.auth.code}</Label>
            <div className="flex gap-2">
              <Input id="otp" inputMode="numeric" pattern="[0-9]*" maxLength={6} value={code}
                     onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} autoComplete="one-time-code" />
              <Button type="submit" variant="outline" disabled={busy || code.length < 6}>{t.auth.verifyCode}</Button>
            </div>
          </form>
        )}
      </div>
    </AuthCard>
  );
}

export default function LoginPage() {
  return <Suspense><LoginForm /></Suspense>;
}
