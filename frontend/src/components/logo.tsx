import { cn } from "@/lib/utils";

export function Logo({ className, withText = true }: { className?: string; withText?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-semibold tracking-tight", className)}>
      <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden>
        <rect width="32" height="32" rx="9" fill="#123D32" />
        <path d="M9 12h14l-1.4 12.2a2 2 0 0 1-2 1.8h-7.2a2 2 0 0 1-2-1.8L9 12Z" fill="#238B67" />
        <path d="M8 10.5h16M13 10.5V9a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1.5" stroke="#B8E986" strokeWidth="1.8" strokeLinecap="round" fill="none" />
        <path d="M16 15.5c-2.6 1.2-3.4 3.6-2.6 6 2.6-.4 4.4-2.3 4.4-5.2" stroke="#B8E986" strokeWidth="1.6" strokeLinecap="round" fill="none" />
      </svg>
      {withText && <span className="text-lg">Waste<span className="text-primary">Wise</span></span>}
    </span>
  );
}
