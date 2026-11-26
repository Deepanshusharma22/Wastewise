import { describe, expect, it } from "vitest";
import { fromDetail, fromPrediction } from "./view-model";
import type { Guidance, HistoryDetail, PredictionResult } from "@/lib/types";

const g = { name: { en: "Plastic", hi: "प्लास्टिक" } } as unknown as Guidance;
const base = {
  id: "p1", created_at: "2026-11-25T10:00:00Z", predicted_category: "plastic", confidence: 0.4, is_confident: false,
  top_predictions: [{ category: "plastic", probability: 0.4 }, { category: "glass", probability: 0.35 }],
  predicted_item: null, guidance: g, notices: [], quality_warnings: [], image_url: null, model_version: "1.0.0",
} as const;

describe("result view-model", () => {
  it("keeps uncertainty information from /predict", () => {
    const vm = fromPrediction({ ...base, uncertainty_reasons: ["low_confidence", "ambiguous_top2"], predicted_item_label: null,
      item_confidence: null, item_candidates: [], image_saved: false, gradcam_image: "data:image/jpeg;base64,xx",
      model_name: "m", inference_time_ms: 12 } as unknown as PredictionResult);
    expect(vm.isConfident).toBe(false);
    expect(vm.reasons).toEqual(["low_confidence", "ambiguous_top2"]);
    expect(vm.gradcam).toMatch(/^data:image\/jpeg/);
  });
  it("maps a stored history record and labels the item from the knowledge base", () => {
    const vm = fromDetail({ ...base, is_confident: true, confidence: 0.9, predicted_item: "plastic_bottle", recyclable: true,
      disposal_instructions: { en: [], hi: [] }, safety_precautions: { en: [], hi: [] }, model_name: "m",
      inference_time_ms: null, feedback: null } as unknown as HistoryDetail);
    expect(vm.itemLabel?.en).toBe("Plastic bottle");
    expect(vm.gradcam).toBeNull();
  });
});
