import type { Bilingual, Category, CategoryProbability, Feedback, Guidance, HistoryDetail, Notice, PredictionResult, QualityWarning } from "@/lib/types";
import { itemLabel } from "@/lib/knowledge";

/** One shape for both a fresh /predict response and a stored /history/{id} record. */
export interface ResultVM {
  id: string;
  createdAt: string;
  category: Category;
  confidence: number;
  isConfident: boolean;
  reasons: string[];
  top: CategoryProbability[];
  item: string | null;
  itemLabel: Bilingual | null;
  itemConfidence: number | null;
  guidance: Guidance;
  notices: Notice[];
  quality: QualityWarning[];
  imageUrl: string | null;
  gradcam: string | null;
  modelVersion: string;
  inferenceMs: number | null;
  feedback: Feedback | null;
}

export function fromPrediction(p: PredictionResult): ResultVM {
  return {
    id: p.id, createdAt: p.created_at, category: p.predicted_category, confidence: p.confidence,
    isConfident: p.is_confident, reasons: p.uncertainty_reasons, top: p.top_predictions,
    item: p.predicted_item, itemLabel: p.predicted_item_label ?? itemLabel(p.predicted_item), itemConfidence: p.item_confidence,
    guidance: p.guidance, notices: p.notices, quality: p.quality_warnings, imageUrl: p.image_url,
    gradcam: p.gradcam_image, modelVersion: p.model_version, inferenceMs: p.inference_time_ms, feedback: null,
  };
}

export function fromDetail(d: HistoryDetail, gradcam: string | null = null): ResultVM {
  return {
    id: d.id, createdAt: d.created_at, category: d.predicted_category, confidence: d.confidence,
    isConfident: d.is_confident, reasons: [], top: d.top_predictions, item: d.predicted_item,
    itemLabel: itemLabel(d.predicted_item), itemConfidence: null, guidance: d.guidance, notices: d.notices,
    quality: d.quality_warnings, imageUrl: d.image_url, gradcam, modelVersion: d.model_version,
    inferenceMs: d.inference_time_ms, feedback: d.feedback,
  };
}

/** The Grad-CAM overlay is never stored server-side; keep it for this browser tab only. */
const KEY = (id: string) => `ww-gradcam-${id}`;
export function stashGradcam(id: string, dataUrl: string | null) {
  if (!dataUrl) return;
  try { sessionStorage.setItem(KEY(id), dataUrl); } catch { /* quota: ignore */ }
}
export function readGradcam(id: string): string | null {
  try { return sessionStorage.getItem(KEY(id)); } catch { return null; }
}
