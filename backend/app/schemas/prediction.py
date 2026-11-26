"""Pydantic response/request models for predictions, history and feedback."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["organic", "paper_cardboard", "plastic", "metal", "glass", "e_waste", "hazardous"]


class Bilingual(BaseModel):
    en: str
    hi: str


class BilingualList(BaseModel):
    en: list[str] = Field(default_factory=list)
    hi: list[str] = Field(default_factory=list)


class CategoryProbability(BaseModel):
    category: Category
    probability: float


class ItemProbability(BaseModel):
    item: str
    probability: float


class Notice(BaseModel):
    """Machine-readable notice that the UI renders (e.g. the hazardous-scope limitation)."""
    code: str
    severity: Literal["info", "warning", "danger"]
    message: Bilingual


class QualityWarning(BaseModel):
    code: Literal["blurry", "too_dark", "too_bright", "low_resolution"]
    message: Bilingual


class Guidance(BaseModel):
    name: Bilingual
    short: Bilingual
    bin: str
    bin_label: Bilingual
    recyclable: str                    # yes | conditional | compostable | authorized | special
    recyclable_label: Bilingual
    color: str
    icon: str
    segregation: BilingualList
    disposal: BilingualList
    recycling: BilingualList
    safety: BilingualList
    common_mistakes: BilingualList
    environment: BilingualList


class PredictionResult(BaseModel):
    id: str
    created_at: datetime
    predicted_category: Category
    confidence: float
    is_confident: bool
    uncertainty_reasons: list[str]
    top_predictions: list[CategoryProbability]
    predicted_item: str | None
    predicted_item_label: Bilingual | None
    item_confidence: float | None
    item_candidates: list[ItemProbability]
    guidance: Guidance
    notices: list[Notice]
    quality_warnings: list[QualityWarning]
    image_url: str | None = Field(None, description="Short-lived signed URL of the stored image")
    image_saved: bool
    gradcam_image: str | None = Field(None, description="data: URL of the Grad-CAM overlay (not stored)")
    model_name: str
    model_version: str
    inference_time_ms: float


class HistoryItem(BaseModel):
    id: str
    created_at: datetime
    predicted_category: Category
    predicted_item: str | None
    confidence: float
    is_confident: bool
    recyclable: bool | None
    image_url: str | None
    model_version: str


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    page: int
    page_size: int
    total: int


class HistoryDetail(HistoryItem):
    top_predictions: list[CategoryProbability]
    uncertainty_reasons: list[str] = Field(default_factory=list)
    disposal_instructions: BilingualList
    safety_precautions: BilingualList
    quality_warnings: list[QualityWarning]
    guidance: Guidance
    notices: list[Notice]
    model_name: str
    inference_time_ms: float | None
    feedback: "FeedbackOut | None" = None


class FeedbackIn(BaseModel):
    user_correctness_feedback: bool
    corrected_category: Literal["organic", "paper_cardboard", "plastic", "metal", "glass", "e_waste",
                                "hazardous", "other"] | None = None
    comments: str | None = Field(None, max_length=1000)


class FeedbackOut(FeedbackIn):
    id: str
    prediction_id: str
    created_at: datetime


HistoryDetail.model_rebuild()
