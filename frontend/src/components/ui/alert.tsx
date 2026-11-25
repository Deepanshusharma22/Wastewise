import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const alertVariants = cva("relative flex gap-3 rounded-lg border p-4 text-sm [&>svg]:mt-0.5 [&>svg]:size-5 [&>svg]:shrink-0", {
  variants: {
    variant: {
      info: "border-primary/30 bg-primary/5 [&>svg]:text-primary",
      warning: "border-warning/40 bg-warning/10 [&>svg]:text-warning",
      danger: "border-destructive/40 bg-destructive/10 [&>svg]:text-destructive",
    },
  },
  defaultVariants: { variant: "info" },
});

export function Alert({ className, variant, ...p }: React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof alertVariants>) {
  return <div role={variant === "danger" ? "alert" : "status"} className={cn(alertVariants({ variant }), className)} {...p} />;
}
export function AlertTitle({ className, ...p }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h5 className={cn("font-semibold leading-tight", className)} {...p} />;
}
export function AlertDescription({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mt-1 text-muted-foreground [&_p]:leading-relaxed", className)} {...p} />;
}
