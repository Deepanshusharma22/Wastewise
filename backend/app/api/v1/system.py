from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from starlette.concurrency import run_in_threadpool

from ...config import Settings, get_settings
from ...database.supabase_client import SupabaseError, SupabaseGateway
from ...ml.model_loader import LoadedModel, registry
from ...schemas.system import HealthResponse, ModelInfo
from ...services import avatar_service, history_service
from ...utils.rate_limit import client_key, limiter
from ...utils.security import AuthUser
from ..deps import ensure_model_loaded, get_current_user, get_gateway, get_model

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Liveness + readiness (model and DB config)")
async def health(response: Response, settings: Settings = Depends(get_settings)):
    await run_in_threadpool(ensure_model_loaded, settings)
    m = registry.model
    ok = m is not None and settings.data_configured
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if ok else "degraded",
        "model_loaded": m is not None,
        # Full exception text (paths, URLs) only outside production; logs always have the details.
        "model_error": (registry.error if settings.environment != "production"
                        else ("model unavailable" if registry.error else None)),
        "model_name": m.name if m else None,
        "model_version": m.version if m else None,
        "supabase_configured": settings.supabase_configured,
        "local_mode": settings.local_mode,
        "environment": settings.environment,
    }


@router.get("/model-info", response_model=ModelInfo, summary="Deployed model version, metrics and limitations")
async def model_info(model: LoadedModel = Depends(get_model)):
    c = model.card
    return {k: c.get(k) for k in ModelInfo.model_fields if k in c}


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT,
               summary="Permanently delete the caller's account, history and stored images")
async def delete_account(request: Request, user: AuthUser = Depends(get_current_user),
                         gw: SupabaseGateway = Depends(get_gateway), settings: Settings = Depends(get_settings)):
    limiter.check("account-delete:" + client_key(request), [(settings.local_account_delete_per_hour, 3600)])
    try:
        await history_service.delete_account_data(gw, settings, user)
    except SupabaseError as exc:
        if exc.status == 503:
            raise HTTPException(503, detail={"code": "not_configured", "message": exc.message})
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/profile/avatar", status_code=status.HTTP_201_CREATED,
            summary="Upload a profile photo (server-generated storage path)")
async def upload_avatar(file: UploadFile = File(..., description="JPG, PNG or WEBP, max 2 MB"),
                        user: AuthUser = Depends(get_current_user),
                        gw: SupabaseGateway = Depends(get_gateway),
                        settings: Settings = Depends(get_settings)):
    from ...utils.validators import ValidationFailure, validate_image_bytes
    data = await file.read(2 * 1024 * 1024 + 1)
    try:
        validate_image_bytes(data, file.content_type, 2 * 1024 * 1024, settings.max_image_pixels, min_side=32)
    except ValidationFailure as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": exc.message})
    content_type = file.content_type if file.content_type in ("image/png", "image/webp") else "image/jpeg"
    path = await avatar_service.replace_avatar(gw, settings, user, data, content_type)
    if settings.local_mode:
        return {"avatar_url": path, "avatar_url_signed": f"{settings.public_base_url}/files/{settings.avatar_bucket}/{path}"}
    signed = await gw.sign_urls(user.token, settings.avatar_bucket, [path], settings.signed_url_ttl_seconds)
    return {"avatar_url": path, "avatar_url_signed": signed.get(path)}
