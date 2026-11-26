"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { Loader2, MailCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthCard, FormError } from "../auth-card";
import { backend, type BackendMode } from "@/lib/backend";
import { useI18n } from "@/lib/i18n/provider";
import { passwordStrongEnough } from "@/lib/validation";

function SignupForm() {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState<{ mode: BackendMode; emailLink: string | null } | null>(null);
  const [resent, setResent] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!passwordStrongEnough(password)) return setError(t.auth.weak);
    if (password !== confirm) return setError(t.auth.mismatch);
    setBusy(true);
    const b = await backend();
    const result = await b.signup({
      email: email.trim(),
      password,
      fullName: name.trim(),
      emailRedirectTo: b.callbackUrl("/dashboard"),
    });
    setBusy(false);
    if (result.error) return setError(result.error.message);
    if (!result.needsConfirmation) {
      // Session already active (email confirmation disabled or local auto-confirm).
      window.location.assign("/dashboard");
      return;
    }
    setSent({ mode: b.mode, emailLink: result.emailLink });
  }

  async function resend() {
    setResent(false);
    setBusy(true);
    const b = await backend();
    const r = await b.resendConfirmation(email.trim(), b.callbackUrl("/dashboard"));
    setBusy(false);
    if (r.alreadyConfirmed) { setError(t.auth.alreadyConfirmed); return; }
    if (!r.ok) { setError(t.common.rateLimited); return; }
    if (r.emailLink) setSent({ mode: b.mode, emailLink: r.emailLink });
    setResent(true);
  }

  if (sent) {
    return (
      <AuthCard title={t.auth.signupTitle}>
        <div className="flex flex-col items-center gap-3 text-center">
          <MailCheck className="h-10 w-10 text-primary" aria-hidden />
          <p role="status">{t.auth.checkEmailBody.replace("{email}", email.trim())}</p>
          {resent && <p className="text-sm text-primary">{t.auth.resent}</p>}
          <FormError message={error} />

          {sent.mode === "local" && sent.emailLink && (
            <div className="w-full space-y-2 rounded-md border border-dashed p-3">
              <p className="text-xs text-muted-foreground">{t.auth.localModeNote}</p>
              <Button asChild className="w-full">
                {/* Local mode has no mailer: the link itself is the "email". */}
                <a href={sent.emailLink}>{t.auth.openLink}</a>
              </Button>
            </div>
          )}

          <div className="flex w-full flex-col gap-2 sm:flex-row">
            <Button variant="outline" className="flex-1" onClick={resend} disabled={busy}>
              {busy && <Loader2 className="animate-spin" />}{t.auth.resend}
            </Button>
            <Button asChild variant="ghost" className="flex-1">
              <Link href={`/login?email=${encodeURIComponent(email.trim())}`}>{t.auth.backToLogin}</Link>
            </Button>
          </div>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard title={t.auth.signupTitle} sub={t.auth.signupSub}
      footer={<>{t.auth.haveAccount} <Link className="font-medium text-primary hover:underline" href="/login">{t.auth.login}</Link></>}>
      <form className="space-y-4" onSubmit={onSubmit} noValidate>
        <FormError message={error} />
        <div className="space-y-1.5">
          <Label htmlFor="name">{t.auth.fullName}</Label>
          <Input id="name" autoComplete="name" maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="email">{t.auth.email}</Label>
          <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">{t.auth.password}</Label>
          <Input id="password" type="password" autoComplete="new-password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} aria-describedby="pw-help" />
          <p id="pw-help" className="text-xs text-muted-foreground">{t.auth.weak}</p>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="confirm">{t.auth.confirmPassword}</Label>
          <Input id="confirm" type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        </div>
        <Button type="submit" className="w-full" disabled={busy || !email || !password}>
          {busy && <Loader2 className="animate-spin" />}{t.auth.signup}
        </Button>
      </form>
    </AuthCard>
  );
}

export default function SignupPage() {
  return <Suspense><SignupForm /></Suspense>;
}
