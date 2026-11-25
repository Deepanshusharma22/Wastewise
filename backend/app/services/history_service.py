"""History listing / detail / deletion (all queries run under the caller's JWT -> RLS)."""
from __future__ import annotations

from datetime import date, timedelta

from ..config import Settings
from ..database.supabase_client import SupabaseError, SupabaseGateway, pg_eq
from ..utils.security import AuthUser
from ..utils.validators import is_owned_storage_path
from . import knowledge

LIST_COLUMNS = "id,created_at,predicted_category,predicted_class,confidence_score,is_confident,recyclable,image_path,model_version"
SORTS = {"newest": "created_at.desc", "oldest": "created_at.asc",
         "confidence_desc": "confidence_score.desc,created_at.desc",
         "confidence_asc": "confidence_score.asc,created_at.desc"}


class NotFound(Exception):
    pass


def _item(row: dict, urls: dict[str, str]) -> dict:
    return {
        "id": row["id"], "created_at": row["created_at"], "predicted_category": row["predicted_category"],
        "predicted_item": row.get("predicted_class"), "confidence": row["confidence_score"],
        "is_confident": row["is_confident"], "recyclable": row.get("recyclable"),
        "image_url": urls.get(row.get("image_path") or ""), "model_version": row["model_version"],
    }


async def list_history(gw: SupabaseGateway, settings: Settings, user: AuthUser, *, page: int, page_size: int,
                       category: str | None, confident: bool | None, date_from: date | None, date_to: date | None,
                       sort: str) -> dict:
    params: dict[str, str] = {"select": LIST_COLUMNS, "user_id": pg_eq(user.id), "order": SORTS[sort]}
    if category:
        params["predicted_category"] = pg_eq(category)
    if confident is not None:
        params["is_confident"] = pg_eq(str(confident).lower())
    and_filters = []
    if date_from:
        and_filters.append(f"created_at.gte.{date_from.isoformat()}")
    if date_to:
        and_filters.append(f"created_at.lt.{(date_to + timedelta(days=1)).isoformat()}")
    if and_filters:
        params["and"] = f"({','.join(and_filters)})"
    start = (page - 1) * page_size
    rows, total = await gw.select(user.token, "predictions", params, count=True,
                                  range_=(start, start + page_size - 1))
    paths = [r["image_path"] for r in rows if is_owned_storage_path(r.get("image_path"), user.id)]
    urls = await gw.sign_urls(user.token, settings.storage_bucket, paths, settings.signed_url_ttl_seconds) if paths else {}
    return {"items": [_item(r, urls) for r in rows], "page": page, "page_size": page_size, "total": total or 0}


async def get_detail(gw: SupabaseGateway, settings: Settings, user: AuthUser, prediction_id: str) -> dict:
    rows, _ = await gw.select(user.token, "predictions", {"select": "*", "id": pg_eq(prediction_id),
                                                          "user_id": pg_eq(user.id)})
    if not rows:
        raise NotFound()
    row = rows[0]
    urls = {}
    if is_owned_storage_path(row.get("image_path"), user.id):
        urls = await gw.sign_urls(user.token, settings.storage_bucket, [row["image_path"]],
                                  settings.signed_url_ttl_seconds)
    fb_rows, _ = await gw.select(user.token, "feedback", {
        "select": "id,prediction_id,user_correctness_feedback,corrected_category,comments,created_at",
        "prediction_id": pg_eq(prediction_id), "user_id": pg_eq(user.id)})
    top_cats = [t["category"] for t in row["top_predictions"]]
    detail = _item(row, urls)
    detail.update({
        "top_predictions": row["top_predictions"],
        "disposal_instructions": row.get("disposal_instructions") or {"en": [], "hi": []},
        "safety_precautions": row.get("safety_precautions") or {"en": [], "hi": []},
        "quality_warnings": row.get("quality_warnings") or [],
        "guidance": knowledge.guidance_for(row["predicted_category"]),
        "notices": knowledge.notices_for(row["predicted_category"], row["is_confident"], top_cats,
                                         row.get("predicted_class")),
        "model_name": row["model_name"], "inference_time_ms": row.get("inference_time_ms"),
        "feedback": fb_rows[0] if fb_rows else None,
    })
    return detail


async def delete_prediction(gw: SupabaseGateway, settings: Settings, user: AuthUser, prediction_id: str) -> None:
    deleted = await gw.delete(user.token, "predictions", {"id": pg_eq(prediction_id), "user_id": pg_eq(user.id)})
    if not deleted:
        raise NotFound()
    path = deleted[0].get("image_path")
    if is_owned_storage_path(path, user.id):
        await gw.remove(user.token, settings.storage_bucket, [path])


async def upsert_feedback(gw: SupabaseGateway, user: AuthUser, prediction_id: str, fb: dict) -> dict:
    # Ensure the prediction exists and belongs to the caller (RLS would also block it).
    rows, _ = await gw.select(user.token, "predictions", {"select": "id", "id": pg_eq(prediction_id),
                                                          "user_id": pg_eq(user.id)})
    if not rows:
        raise NotFound()
    existing, _ = await gw.select(user.token, "feedback", {"select": "id", "prediction_id": pg_eq(prediction_id),
                                                           "user_id": pg_eq(user.id)})
    cols = "id,prediction_id,user_correctness_feedback,corrected_category,comments,created_at"
    if existing:
        updated = await gw.update(user.token, "feedback", {"id": pg_eq(existing[0]["id"]), "select": cols}, fb)
        return updated[0]
    return await gw.insert(user.token, "feedback", {"user_id": user.id, "prediction_id": prediction_id, **fb})


async def delete_account_data(gw: SupabaseGateway, settings: Settings, user: AuthUser) -> int:
    """Remove every stored image of the user, then the auth user (rows cascade via FK on delete)."""
    paths: list[str] = []
    offset = 0
    while True:
        rows, _ = await gw.select(user.token, "predictions", {"select": "image_path", "user_id": pg_eq(user.id),
                                                              "image_path": "not.is.null"},
                                  range_=(offset, offset + 999))
        paths += [r["image_path"] for r in rows if is_owned_storage_path(r["image_path"], user.id)]
        if len(rows) < 1000:
            break
        offset += 1000
    for i in range(0, len(paths), 100):
        await gw.remove(user.token, settings.storage_bucket, paths[i:i + 100])
    try:
        prof, _ = await gw.select(user.token, "profiles", {"select": "avatar_url", "id": pg_eq(user.id)})
        if prof and is_owned_storage_path(prof[0].get("avatar_url"), user.id):
            await gw.remove(user.token, settings.avatar_bucket, [prof[0]["avatar_url"]])
    except SupabaseError:
        pass
    await gw.delete_auth_user(user.id)
    return len(paths)
