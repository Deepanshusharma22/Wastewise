"""Shared FastAPI dependencies."""
from __future__ import annotations

import threading

import httpx
from fastapi import Depends, HTTPException, Request, status

from ..config import Settings, get_settings
from ..database.supabase_client import SupabaseGateway
from ..ml.model_loader import LoadedModel, registry
from ..utils.rate_limit import client_key, limiter
from ..utils.security import AuthUser, get_current_user


_init_lock = threading.Lock()
_model_attempted = False


def ensure_model_loaded(settings: Settings) -> None:
    """Load the model once per process even if the ASGI lifespan never ran (serverless runtimes)."""
    global _model_attempted
    if registry.model is not None or _model_attempted:
        return
    with _init_lock:
        if registry.model is None and not _model_attempted:
            registry.load(settings.model_dir)
            _model_attempted = True


def mark_model_attempted() -> None:
    global _model_attempted
    _model_attempted = True


def get_gateway(request: Request, settings: Settings = Depends(get_settings)) -> SupabaseGateway:
    gw = getattr(request.app.state, "gateway", None)
    if gw is None and settings.supabase_configured:
        # lifespan did not run (e.g. serverless): create the shared client lazily
        with _init_lock:
            gw = getattr(request.app.state, "gateway", None)
            if gw is None:
                http = httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0))
                gw = SupabaseGateway(settings.supabase_url, settings.supabase_anon_key,
                                     settings.supabase_service_role_key, http)
                request.app.state.gateway = gw
    if gw is None or not settings.supabase_configured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail={"code": "database_unavailable", "message": "The database is not configured."})
    return gw


def get_model(settings: Settings = Depends(get_settings)) -> LoadedModel:
    ensure_model_loaded(settings)
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
