"""WasteWise API entry point.

Run locally:  uvicorn app.main:app --reload --port 8000   (from backend/)
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .api.deps import mark_model_attempted
from .api.v1 import analytics, history, predict, system
from .config import get_settings
from .database.supabase_client import SupabaseError, SupabaseGateway
from .ml.model_loader import registry

settings = get_settings()
logging.basicConfig(level=settings.log_level.upper(),
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("wastewise")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    await run_in_threadpool(registry.load, s.model_dir)   # load the model exactly once per process
    mark_model_attempted()
    http = httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0),
                             limits=httpx.Limits(max_connections=50, max_keepalive_connections=20))
    app.state.gateway = (SupabaseGateway(s.supabase_url, s.supabase_anon_key, s.supabase_service_role_key, http)
                         if s.supabase_configured else None)
    if not s.supabase_configured:
        log.warning("SUPABASE_URL / SUPABASE_ANON_KEY not set: data endpoints will return 503")
    try:
        yield
    finally:
        await http.aclose()


app = FastAPI(
    title="WasteWise API",
    version="1.0.0",
    description="AI waste classification, segregation guidance and per-user history. "
                "All data endpoints require a Supabase access token (Authorization: Bearer <jwt>).",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=False,          # bearer tokens, no cookies
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    max_age=600,
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    request.state.request_id = rid
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
    # never log tokens, bodies or user ids — only route, status and latency
    log.info("%s %s %s %.0fms rid=%s", request.method, request.url.path, response.status_code, ms, rid)
    return response


def _error(status: int, code: str, message: str, request: Request, headers: dict | None = None, **extra):
    body = {"error": {"code": code, "message": message, "request_id": getattr(request.state, "request_id", None),
                      **extra}}
    return JSONResponse(body, status_code=status, headers=headers)


@app.exception_handler(HTTPException)
async def http_exc(request: Request, exc: HTTPException):
    d = exc.detail
    if isinstance(d, dict):
        return _error(exc.status_code, d.get("code", "error"), d.get("message", ""), request, exc.headers)
    return _error(exc.status_code, "error", str(d), request, exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exc(request: Request, exc: RequestValidationError):
    fields = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return _error(422, "validation_error", "Some request fields are invalid.", request, fields=fields)


@app.exception_handler(SupabaseError)
async def supabase_exc(request: Request, exc: SupabaseError):
    log.warning("supabase error %s: %s", exc.status, exc.message)
    if exc.status == 401:
        return _error(401, "not_authenticated", "Your session is no longer valid. Please sign in again.", request)
    if exc.status == 403:
        return _error(403, "forbidden", "You are not allowed to access this resource.", request)
    if exc.status == 413:
        return _error(413, "file_too_large", "The image is too large to store.", request)
    return _error(502, "upstream_error", "A storage or database request failed. Please try again.", request)


@app.exception_handler(Exception)
async def unhandled_exc(request: Request, exc: Exception):
    log.exception("unhandled error")
    return _error(500, "internal_error", "Something went wrong on our side.", request)


api_prefix = "/api/v1"
for r in (system.router, predict.router, history.router, analytics.router):
    app.include_router(r, prefix=api_prefix)


@app.get("/", include_in_schema=False)
async def root():
    return {"name": "WasteWise API", "docs": "/docs", "health": f"{api_prefix}/health"}


@app.get("/livez", include_in_schema=False)
async def livez():
    """Process liveness for container orchestrators (does not depend on model/DB)."""
    return {"status": "alive"}
