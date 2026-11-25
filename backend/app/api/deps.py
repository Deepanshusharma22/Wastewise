"""Shared FastAPI dependencies."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from ..config import Settings, get_settings
from ..database.supabase_client import SupabaseGateway
from ..ml.model_loader import LoadedModel, registry
from ..utils.rate_limit import client_key, limiter
from ..utils.security import AuthUser, get_current_user


def get_gateway(request: Request, settings: Settings = Depends(get_settings)) -> SupabaseGateway:
    gw = getattr(request.app.state, "gateway", None)
    if gw is None or not settings.supabase_configured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail={"code": "database_unavailable", "message": "The database is not configured."})
    return gw


def get_model() -> LoadedModel:
    model = registry.model
    if model is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail={"code": "model_unavailable",
                                    "message": "The classification model is not available. Please try again later."})
    return model


def predict_rate_limit(request: Request, user: AuthUser = Depends(get_current_user),
                       settings: Settings = Depends(get_settings)) -> AuthUser:
    limiter.check("predict:" + client_key(request),
                  [(settings.predict_rate_per_minute, 60), (settings.predict_rate_per_day, 86_400)])
    return user
