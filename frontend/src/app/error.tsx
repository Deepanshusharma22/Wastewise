"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n/provider";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const { t } = useI18n();
  useEffect(() => { console.error(error); }, [error]);
  return (
    <div role="alert" className="mx-auto flex max-w-md flex-col items-center px-4 py-24 text-center">
      <h1 className="text-2xl font-bold">{t.common.error}</h1>
      {error.digest && <p className="mt-2 text-xs text-muted-foreground">ref: {error.digest}</p>}
      <Button className="mt-6" onClick={reset}>{t.common.retry}</Button>
    </div>
  );
}
