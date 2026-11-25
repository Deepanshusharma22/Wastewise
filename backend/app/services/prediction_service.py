"""Predict -> store image -> persist record -> build the API response."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from PIL import Image
from starlette.concurrency import run_in_threadpool

from ..config import Settings
from ..database.supabase_client import SupabaseError, SupabaseGateway, pg_eq
from ..ml import inference
from ..ml.model_loader import LoadedModel
from ..utils.security import AuthUser
from . import image_service, knowledge

log = logging.getLogger("wastewise.predict")


def _infer(model: LoadedModel, img: Image.Image, threshold_override: float | None):
    """CPU-bound part: runs in a worker thread so the event loop stays responsive."""
    res = inference.predict(model, img, threshold_override)
    cam_url = None
    try:
        cam = inference.gradcam(model, res.features, res.category)
        cam_url = inference.gradcam_overlay_png(model, img, cam)
    except Exception:  # Grad-CAM is an explanation aid; never fail the prediction because of it
        log.exception("grad-cam failed")
    warnings = image_service.quality_warnings(img)
    return res, cam_url, warnings


async def _user_wants_images_saved(gw: SupabaseGateway, user: AuthUser) -> bool:
    try:
        rows, _ = await gw.select(user.token, "profiles", {"id": pg_eq(user.id), "select": "save_images"})
        return bool(rows[0]["save_images"]) if rows else True
    except SupabaseError:
        log.warning("could not read profile preferences; defaulting to save_images=true")
        return True


async def create_prediction(gw: SupabaseGateway, settings: Settings, model: LoadedModel, user: AuthUser,
                            img: Image.Image) -> dict:
    res, cam_url, warnings = await run_in_threadpool(_infer, model, img, settings.confidence_threshold_override)

    prediction_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    guidance = knowledge.guidance_for(res.category)
    top_cats = [t["category"] for t in res.top_predictions]
    notices = knowledge.notices_for(res.category, res.is_confident, top_cats, res.item)

    image_path: str | None = None
    if await _user_wants_images_saved(gw, user):
        data = await run_in_threadpool(image_service.encode_for_storage, img, settings.stored_image_max_side)
        image_path = image_service.storage_path(user.id, prediction_id, now)
        await gw.upload(user.token, settings.storage_bucket, image_path, data, "image/jpeg")

    row = {
        "id": prediction_id,
        "user_id": user.id,
        "image_path": image_path,
        "predicted_category": res.category,
        "predicted_class": res.item,
        "confidence_score": round(res.confidence, 6),
        "is_confident": res.is_confident,
        "top_predictions": res.top_predictions,
        "disposal_instructions": guidance["disposal"],
        "safety_precautions": guidance["safety"],
        "recyclable": knowledge.is_recyclable(res.category),
        "quality_warnings": warnings,
        "model_name": model.name,
        "model_version": model.version,
        "inference_time_ms": res.inference_time_ms,
    }
    try:
        saved = await gw.insert(user.token, "predictions", row)
    except SupabaseError:
        if image_path:  # compensate: do not leave an orphaned image behind
            try:
                await gw.remove(user.token, settings.storage_bucket, [image_path])
            except SupabaseError:
                log.exception("failed to clean up orphaned image %s", image_path)
        raise

    image_url = None
    if image_path:
        signed = await gw.sign_urls(user.token, settings.storage_bucket, [image_path], settings.signed_url_ttl_seconds)
        image_url = signed.get(image_path)

    return {
        "id": prediction_id,
        "created_at": saved.get("created_at", now.isoformat()),
        "predicted_category": res.category,
        "confidence": res.confidence,
        "is_confident": res.is_confident,
        "uncertainty_reasons": res.reasons,
        "top_predictions": res.top_predictions,
        "predicted_item": res.item,
        "predicted_item_label": knowledge.item_label(res.item),
        "item_confidence": res.item_confidence,
        "item_candidates": res.item_candidates,
        "guidance": guidance,
        "notices": notices,
        "quality_warnings": warnings,
        "image_url": image_url,
        "image_saved": image_path is not None,
        "gradcam_image": cam_url,
        "model_name": model.name,
        "model_version": model.version,
        "inference_time_ms": res.inference_time_ms,
    }
