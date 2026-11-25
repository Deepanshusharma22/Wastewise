from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from ...config import Settings, get_settings
from ...database.supabase_client import SupabaseGateway
from ...ml.model_loader import LoadedModel
from ...schemas.prediction import PredictionResult
from ...services import prediction_service
from ...utils.security import AuthUser
from ...utils.validators import ValidationFailure, validate_image_bytes
from ..deps import get_gateway, get_model, predict_rate_limit

router = APIRouter(tags=["prediction"])


@router.post("/predict", response_model=PredictionResult, status_code=status.HTTP_201_CREATED,
             summary="Classify a waste image, store it in the user's history and return guidance")
async def predict(
    file: UploadFile = File(..., description="JPG, PNG or WEBP image, max 4 MB"),
    user: AuthUser = Depends(predict_rate_limit),
    model: LoadedModel = Depends(get_model),
    gw: SupabaseGateway = Depends(get_gateway),
    settings: Settings = Depends(get_settings),
):
    data = await file.read(settings.max_upload_bytes + 1)   # bounded read: never buffer more than limit+1
    try:
        img = await run_in_threadpool(validate_image_bytes, data, file.content_type, settings.max_upload_bytes,
                                      settings.max_image_pixels)
    except ValidationFailure as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": exc.message})
    return await prediction_service.create_prediction(gw, settings, model, user, img)
