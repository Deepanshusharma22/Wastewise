from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str                 # ok | degraded
    model_loaded: bool
    model_error: str | None
    model_name: str | None
    model_version: str | None
    supabase_configured: bool
    environment: str


class ModelInfo(BaseModel):
    """Public subset of backend/model_artifacts/model_card.json (written by ml/src/select_model.py)."""
    model_name: str
    model_version: str
    architecture: str
    dataset_version: str | None = None
    exported_at: str | None = None
    categories: list[str]
    items: list[str]
    confidence_threshold: float
    temperature: float
    metrics: dict
    latency: dict = {}
    training_data: list[dict] = []
    limitations: list[str] = []
