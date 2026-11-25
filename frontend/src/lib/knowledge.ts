import data from "@/data/waste_knowledge.json";
import type { Bilingual, BilingualList, Category } from "./types";

export interface CategoryKnowledge {
  color: string; icon: string; bin: string; recyclable: string;
  name: Bilingual; short: Bilingual; description: Bilingual; examples: BilingualList;
  segregation: BilingualList; disposal: BilingualList; recycling: BilingualList; safety: BilingualList;
  common_mistakes: BilingualList; environment: BilingualList; [k: string]: unknown;
}
interface Knowledge {
  version: string; note: string;
  categories: Record<Category, CategoryKnowledge>;
  items: Record<string, Bilingual & { category?: string }>;
  recyclable_labels: Record<string, Bilingual>;
  bins: Record<string, Bilingual | { label: Bilingual; [k: string]: unknown }>;
}

export const knowledge = data as unknown as Knowledge;

export function categoryInfo(c: string): CategoryKnowledge | undefined {
  return (knowledge.categories as Record<string, CategoryKnowledge>)[c];
}
export function itemLabel(item: string | null | undefined): Bilingual | null {
  if (!item) return null;
  const v = knowledge.items[item];
  return v ? { en: v.en, hi: v.hi } : { en: item.replace(/_/g, " "), hi: item.replace(/_/g, " ") };
}
export function binLabel(bin: string): Bilingual {
  const b = knowledge.bins[bin] as { en?: string; hi?: string; label?: Bilingual } | undefined;
  if (!b) return { en: bin, hi: bin };
  if (b.label) return b.label;
  return { en: b.en ?? bin, hi: b.hi ?? bin };
}
