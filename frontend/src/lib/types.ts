// Mirrors backend/app/schemas/*.py - keep in sync.
export const CATEGORIES = ["organic", "paper_cardboard", "plastic", "metal", "glass", "e_waste", "hazardous"] as const;
export type Category = (typeof CATEGORIES)[number];
export type Lang = "en" | "hi";

export interface Bilingual { en: string; hi: string }
export interface BilingualList { en: string[]; hi: string[] }
export interface CategoryProbability { category: Category; probability: number }
export interface ItemProbability { item: string; probability: number }
export interface Notice { code: string; severity: "info" | "warning" | "danger"; message: Bilingual }
export interface QualityWarning { code: "blurry" | "too_dark" | "too_bright" | "low_resolution"; message: Bilingual }

export interface Guidance {
  name: Bilingual; short: Bilingual; bin: string; bin_label: Bilingual;
  recyclable: string; recyclable_label: Bilingual; color: string; icon: string;
  segregation: BilingualList; disposal: BilingualList; recycling: BilingualList;
  safety: BilingualList; common_mistakes: BilingualList; environment: BilingualList;
}

export interface PredictionResult {
  id: string; created_at: string;
  predicted_category: Category; confidence: number; is_confident: boolean; uncertainty_reasons: string[];
  top_predictions: CategoryProbability[];
  predicted_item: string | null; predicted_item_label: Bilingual | null; item_confidence: number | null;
  item_candidates: ItemProbability[];
  guidance: Guidance; notices: Notice[]; quality_warnings: QualityWarning[];
  image_url: string | null; image_saved: boolean; gradcam_image: string | null;
  model_name: string; model_version: string; inference_time_ms: number;
}

export interface HistoryItem {
  id: string; created_at: string; predicted_category: Category; predicted_item: string | null;
  confidence: number; is_confident: boolean; recyclable: boolean | null; image_url: string | null; model_version: string;
}
export interface HistoryPage { items: HistoryItem[]; page: number; page_size: number; total: number }

export interface Feedback {
  id: string; prediction_id: string; created_at: string;
  user_correctness_feedback: boolean; corrected_category: Category | "other" | null; comments: string | null;
}
export interface HistoryDetail extends HistoryItem {
  top_predictions: CategoryProbability[]; uncertainty_reasons?: string[]; disposal_instructions: BilingualList; safety_precautions: BilingualList;
  quality_warnings: QualityWarning[]; guidance: Guidance; notices: Notice[]; model_name: string;
  inference_time_ms: number | null; feedback: Feedback | null;
}

export interface CategoryCount { category: string; count: number; percentage: number }
export interface AnalyticsSummary {
  total_scans: number; confident_scans: number; uncertain_scans: number; recyclable_scans: number;
  hazardous_or_ewaste_scans: number; average_confidence: number | null; most_common_category: string | null;
  scans_last_7_days: number; scans_last_30_days: number;
  category_distribution: CategoryCount[]; daily_counts: { date: string; count: number }[]; truncated: boolean;
}

export interface ModelInfo {
  model_name: string; model_version: string; architecture: string; dataset_version?: string | null;
  exported_at?: string | null; categories: string[]; items: string[]; confidence_threshold: number;
  temperature: number; metrics: Record<string, unknown>; latency: Record<string, unknown>;
  training_data: Record<string, unknown>[]; limitations: string[];
}

export interface Profile {
  id: string; full_name: string | null; email: string | null; avatar_url: string | null;
  preferred_language: Lang; theme: "light" | "dark" | "system"; save_images: boolean;
  /** Local mode only: a directly usable URL for the stored avatar. */
  avatar_signed_url?: string | null;
}
