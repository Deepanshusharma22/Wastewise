"use client";

import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n/provider";
import { ApiError, errorKey } from "@/lib/api";

export function useErrorMessage() {
  const { t } = useI18n();
  return (e: unknown) => {
    const k = errorKey(e);
    if (k) return t.common[k];
    if (e instanceof ApiError) return e.message;
    return t.common.error;
  };
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n();
  const msg = useErrorMessage()(error);
  return (
    <div role="alert" className="flex flex-col items-center gap-3 rounded-lg border border-dashed p-8 text-center">
      <AlertCircle className="h-8 w-8 text-destructive" aria-hidden />
      <p className="text-sm text-muted-foreground">{msg}</p>
      {onRetry && <Button variant="outline" size="sm" onClick={onRetry}><RefreshCw />{t.common.retry}</Button>}
    </div>
  );
}
