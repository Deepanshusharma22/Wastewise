"""Per-user analytics computed from the user's own prediction rows (RLS-scoped)."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from ..database.supabase_client import SupabaseGateway, pg_eq
from ..utils.security import AuthUser

CATEGORIES = ["organic", "paper_cardboard", "plastic", "metal", "glass", "e_waste", "hazardous"]
MAX_ROWS = 5000


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def summarise(rows: list[dict], now: datetime | None = None, truncated: bool = False) -> dict:
    now = now or datetime.now(timezone.utc)
    total = len(rows)
    counts = Counter(r["predicted_category"] for r in rows)
    confident = sum(1 for r in rows if r["is_confident"])
    stamps = [_parse(r["created_at"]) for r in rows]
    today = now.date()
    days = [today - timedelta(days=i) for i in range(29, -1, -1)]
    per_day = Counter(s.date() for s in stamps)
    return {
        "total_scans": total,
        "confident_scans": confident,
        "uncertain_scans": total - confident,
        "recyclable_scans": sum(1 for r in rows if r.get("recyclable")),
        "hazardous_or_ewaste_scans": counts["hazardous"] + counts["e_waste"],
        "average_confidence": round(sum(r["confidence_score"] for r in rows) / total, 4) if total else None,
        "most_common_category": counts.most_common(1)[0][0] if total else None,
        "scans_last_7_days": sum(1 for s in stamps if s >= now - timedelta(days=7)),
        "scans_last_30_days": sum(1 for s in stamps if s >= now - timedelta(days=30)),
        "category_distribution": [
            {"category": c, "count": counts[c], "percentage": round(100 * counts[c] / total, 1) if total else 0.0}
            for c in CATEGORIES
        ],
        "daily_counts": [{"date": d.isoformat(), "count": per_day[d]} for d in days],
        "truncated": truncated,
    }


async def fetch_rows(gw: SupabaseGateway, user: AuthUser) -> tuple[list[dict], bool]:
    rows, total = await gw.select(user.token, "predictions", {
        "select": "predicted_category,confidence_score,is_confident,recyclable,created_at",
        "user_id": pg_eq(user.id), "order": "created_at.desc"}, count=True, range_=(0, MAX_ROWS - 1))
    return rows, bool(total and total > len(rows))


async def user_analytics(gw: SupabaseGateway, user: AuthUser) -> dict:
    rows, truncated = await fetch_rows(gw, user)
    return summarise(rows, truncated=truncated)
