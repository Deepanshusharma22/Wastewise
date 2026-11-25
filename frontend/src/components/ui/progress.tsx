"use client";
import * as React from "react";
import * as ProgressPrimitive from "@radix-ui/react-progress";
import { cn } from "@/lib/utils";

export function Progress({ value, className, indicatorClassName, indicatorStyle, ...p }:
  React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> & { indicatorClassName?: string; indicatorStyle?: React.CSSProperties }) {
  const v = Math.max(0, Math.min(100, value ?? 0));
  return (
    <ProgressPrimitive.Root value={v} className={cn("relative h-2 w-full overflow-hidden rounded-full bg-muted", className)} {...p}>
      <ProgressPrimitive.Indicator
        className={cn("h-full bg-primary transition-transform duration-500", indicatorClassName)}
        style={{ transform: `translateX(-${100 - v}%)`, ...indicatorStyle }}
      />
    </ProgressPrimitive.Root>
  );
}
