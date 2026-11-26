"""Shared FastAPI dependencies."""
from __future__ import annotations

import threading

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from ..config import Settings, get_settings
from ..database.local_store import LocalStore
from ..database.supabase_client import SupabaseGateway
from ..ml.model_loader import LoadedModel, registry
from ..utils.rate_limit import client_key, limiter
from ..utils.security import AuthUser, authenticate_bearer, bearer, get_verifier


_init_lock = threading.Lock()
_model_attempted = False


def ensure_model_loaded(settings: Settings) -> None:
    """Load the model once per process even if the ASGI lifespan never ran (serverless runtimes)."""
    global _model_attempted
    if registry.model is not None or _model_attempted:
        return
    with _init_lock:
        if registry.model is None and not _model_attempted:
            registry.load(settings.model_dir, settings.model_base_url)
            _model_attempted = True


def mark_model_attempted() -> None:
    global _model_attempted
    _model_attempted = True


def get_local_store(request: Request, settings: Settings = Depends(get_settings)) -> LocalStore:
    """SQLite data layer used when LOCAL_MODE=1 (no Supabase required)."""
    if not settings.local_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "Not available."})
    store = getattr(request.app.state, "local_store", None)
    if store is None:
        with _init_lock:
            store = getattr(request.app.state, "local_store", None)
            if store is None:
                store = LocalStore(settings.local_db_path, settings.local_storage_dir, settings.public_base_url)
                request.app.state.local_store = store
    return store


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    verifier=Depends(get_verifier),
    settings: Settings = Depends(get_settings),
) -> AuthUser:
    """Resolve the caller from the bearer token: local JWT in local mode, Supabase JWT otherwise."""
    if settings.local_mode:
        from ..utils.local_auth import verify_local_token

        if creds is None or creds.scheme.lower() != "bearer" or not creds.credentials:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                                detail={"code": "not_authenticated", "message": "Sign in to continue."},
                                headers={"WWW-Authenticate": "Bearer"})
        claims = verify_local_token(settings, creds.credentials)
        user = AuthUser(id=claims["sub"], email=claims.get("email"), token=creds.credentials, role="authenticated")
        request.state.user_id = user.id
        return user
    return authenticate_bearer(request, creds, verifier)


def get_gateway(request: Request, settings: Settings = Depends(get_settings)) -> SupabaseGateway:
    # local mode: the SQLite store implements the same interface
    if settings.local_mode:
        return get_local_store(request, settings)  # type: ignore[return-value]
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
    if gw is None or not settings.data_configured:
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
