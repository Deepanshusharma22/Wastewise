"use client";

import { AlertTriangle, Camera, Info, ShieldAlert } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useI18n } from "@/lib/i18n/provider";
import type { Notice, QualityWarning } from "@/lib/types";

export function NoticeList({ notices }: { notices: Notice[] }) {
  const { pick } = useI18n();
  const list = notices.filter((n) => n.code !== "uncertain"); // the uncertain banner is rendered separately
  if (!list.length) return null;
  return (
    <div className="space-y-3">
      {list.map((n) => {
        const Icon = n.severity === "danger" ? ShieldAlert : n.severity === "warning" ? AlertTriangle : Info;
        return (
          <Alert key={n.code} variant={n.severity === "danger" ? "danger" : n.severity === "warning" ? "warning" : "info"}>
            <Icon />
            <AlertDescription className="mt-0 text-foreground">{pick(n.message)}</AlertDescription>
          </Alert>
        );
      })}
    </div>
  );
}

export function QualityWarnings({ warnings }: { warnings: QualityWarning[] }) {
  const { t, pick } = useI18n();
  if (!warnings.length) return null;
  return (
    <Alert variant="warning">
      <Camera />
      <div>
        <AlertTitle>{t.result.quality}</AlertTitle>
        <AlertDescription>
          <ul className="list-disc space-y-0.5 pl-4">{warnings.map((w) => <li key={w.code}>{pick(w.message)}</li>)}</ul>
        </AlertDescription>
      </div>
    </Alert>
  );
}
