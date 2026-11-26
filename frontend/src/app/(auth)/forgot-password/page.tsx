"use client";

import Link from "next/link";
import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthCard, FormError } from "../auth-card";
import { backend } from "@/lib/backend";
import { useI18n } from "@/lib/i18n/provider";

export default function ForgotPasswordPage() {
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [localLink, setLocalLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const b = await backend();
    const r = await b.requestReset(email.trim(), b.callbackUrl("/reset-password"));
    setBusy(false);
    // Never reveal whether the address exists.
    if (!r.ok) { setError(t.common.error); return; }
    setSent(true);
    setLocalLink(r.emailLink);
  }

  return (
    <AuthCard title={t.auth.resetTitle} sub={t.auth.resetSub}
      footer={<Link className="font-medium text-primary hover:underline" href="/login">{t.auth.backToLogin}</Link>}>
      {sent ? (
        <div className="space-y-3">
          <p role="status" className="rounded-md bg-accent p-3 text-sm">{t.auth.resetSent}</p>
          {localLink && (
            <>
              <p className="text-xs text-muted-foreground">{t.auth.localModeNote}</p>
              <Button asChild className="w-full"><a href={localLink}>{t.auth.openLink}</a></Button>
            </>
          )}
        </div>
      ) : (
        <form className="space-y-4" onSubmit={onSubmit}>
          <FormError message={error} />
          <div className="space-y-1.5">
            <Label htmlFor="email">{t.auth.email}</Label>
            <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <Button type="submit" className="w-full" disabled={busy || !email}>{busy && <Loader2 className="animate-spin" />}{t.auth.sendLink}</Button>
        </form>
      )}
    </AuthCard>
  );
}
