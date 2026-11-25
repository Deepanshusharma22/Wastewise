"""Application settings (12-factor: everything comes from environment variables)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "WasteWise API"
    environment: str = Field("development", description="development | production | test")
    log_level: str = "INFO"

    # --- Supabase -----------------------------------------------------------------
    supabase_url: str = ""
    supabase_anon_key: str = ""            # public key, used with the caller's JWT so RLS applies
    supabase_service_role_key: str = ""    # server-only; used exclusively for account deletion
    supabase_jwt_secret: str = ""          # optional: legacy HS256 projects
    supabase_jwks: str = ""                # optional: static JWKS JSON (skips network fetch)
    storage_bucket: str = "waste-images"
    avatar_bucket: str = "avatars"
    signed_url_ttl_seconds: int = 3600

    # --- CORS ---------------------------------------------------------------------
    cors_origins: str = "http://localhost:3000"
    cors_origin_regex: str = ""            # e.g. ^https://wastewise-.*\.vercel\.app$

    # --- uploads & inference -------------------------------------------------------
    max_upload_mb: float = 4.0
    max_image_pixels: int = 40_000_000
    stored_image_max_side: int = 1280
    model_dir: str = str(BACKEND_DIR / "model_artifacts")
    confidence_threshold_override: float | None = None

    # --- rate limiting -------------------------------------------------------------
    predict_rate_per_minute: int = 10
    predict_rate_per_day: int = 300

    @field_validator("supabase_url")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.rstrip("/")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)


@lru_cache
def get_settings() -> Settings:
    return Settings()
