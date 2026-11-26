import { Apple, Battery, CupSoda, Cylinder, FileText, FlaskConical, Leaf, Package, Recycle, SprayCan, Wine, Cpu, TriangleAlert, Newspaper } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { categoryInfo } from "@/lib/knowledge";
import { cn } from "@/lib/utils";

const ICONS: Record<string, LucideIcon> = {
  leaf: Leaf, apple: Apple, "file-text": FileText, newspaper: Newspaper, package: Package, "cup-soda": CupSoda,
  recycle: Recycle, cylinder: Cylinder, wine: Wine, cpu: Cpu, battery: Battery, "spray-can": SprayCan, "flask-conical": FlaskConical,
  "triangle-alert": TriangleAlert,
};
const FALLBACK: Record<string, LucideIcon> = {
  organic: Leaf, paper_cardboard: Newspaper, plastic: CupSoda, metal: Cylinder, glass: Wine, e_waste: Cpu, hazardous: SprayCan,
};

export function categoryColor(category: string): string {
  return categoryInfo(category)?.color ?? "#238B67";
}

export function CategoryIcon({ category, className, boxed = false }: { category: string; className?: string; boxed?: boolean }) {
  const info = categoryInfo(category);
  const Icon = (info && ICONS[info.icon]) || FALLBACK[category] || Recycle;
  const color = categoryColor(category);
  if (!boxed) return <Icon className={className} style={{ color }} aria-hidden />;
  return (
    <span
      className={cn("inline-flex items-center justify-center rounded-lg", className ?? "h-10 w-10")}
      style={{ backgroundColor: `${color}22`, color }}
      aria-hidden
    >
      <Icon className="h-1/2 w-1/2" />
    </span>
  );
}
