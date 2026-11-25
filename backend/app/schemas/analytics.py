from __future__ import annotations

from pydantic import BaseModel


class CategoryCount(BaseModel):
    category: str
    count: int
    percentage: float


class DailyCount(BaseModel):
    date: str          # YYYY-MM-DD (UTC)
    count: int


class AnalyticsSummary(BaseModel):
    total_scans: int
    confident_scans: int
    uncertain_scans: int
    recyclable_scans: int
    hazardous_or_ewaste_scans: int
    average_confidence: float | None
    most_common_category: str | None
    scans_last_7_days: int
    scans_last_30_days: int
    category_distribution: list[CategoryCount]
    daily_counts: list[DailyCount]      # last 30 days, zero-filled
    truncated: bool                      # True if more rows exist than were aggregated
