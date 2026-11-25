"use client";

import { useState } from "react";
import { ImageOff } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/lib/i18n/provider";

/* eslint-disable @next/next/no-img-element -- signed Supabase URLs and data: URLs are not optimisable */
export function GradcamViewer({ imageUrl, gradcam }: { imageUrl: string | null; gradcam: string | null }) {
  const { t } = useI18n();
  const [tab, setTab] = useState(gradcam ? "heatmap" : "original");
  const frame = "aspect-square w-full overflow-hidden rounded-lg border bg-muted";
  return (
    <div>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="heatmap">{t.result.heatmap}</TabsTrigger>
          <TabsTrigger value="original">{t.result.original}</TabsTrigger>
        </TabsList>
        <TabsContent value="heatmap">
          {gradcam ? (
            <figure>
              <img src={gradcam} alt={t.result.gradcamAlt} className={`${frame} object-cover`} />
              <figcaption className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                <span className="h-2 w-16 rounded-full" style={{ background: "linear-gradient(90deg,#000004,#56106e,#bb3754,#f98e09,#fcffa4)" }} aria-hidden />
                {t.result.gradcamHelp}
              </figcaption>
            </figure>
          ) : (
            <div className={`${frame} flex items-center justify-center p-6 text-center text-sm text-muted-foreground`}>{t.result.gradcamMissing}</div>
          )}
        </TabsContent>
        <TabsContent value="original">
          {imageUrl ? (
            <img src={imageUrl} alt={t.result.original} className={`${frame} object-contain`} />
          ) : (
            <div className={`${frame} flex flex-col items-center justify-center gap-2 text-sm text-muted-foreground`}>
              <ImageOff className="h-8 w-8" aria-hidden />{t.result.noImage}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
