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
    # --- local mode (no Supabase needed: SQLite + built-in auth + filesystem storage) -------------
    # Turn on with LOCAL_MODE=1. Never enable in production: it bypasses Supabase entirely.
    local_mode: bool = False
    local_db_path: str = str(BACKEND_DIR / ".local" / "wastewise.db")
    local_storage_dir: str = str(BACKEND_DIR / ".local" / "storage")
    local_jwt_secret: str = "wastewise-local-dev-secret-change-me"
    local_token_ttl_seconds: int = 604800          # 7 days
    local_auto_confirm: bool = True                # skip the email step for local accounts
    # Empty => local file URLs are relative ("/files/..."), which is what you want behind
    # a dev proxy or preview host. Set an absolute URL only if the API is on another origin.
    public_base_url: str = ""
    # local-mode auth limits (per IP); generous defaults, lowered for production-like demos
    local_signup_per_hour: int = 20
    local_login_per_5min: int = 30
    local_resend_per_5min: int = 5
    local_recover_per_hour: int = 10
    local_account_delete_per_hour: int = 5

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
    # Optional commit-pinned URL to fetch wastewise.onnx / gradcam_head.npz from when they are not
    # bundled (verified against model_card.json checksums). Empty = use the bundled files only.
    model_base_url: str = ""
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
    def data_configured(self) -> bool:
        """True when the data layer can serve requests (Supabase or local mode)."""
        return self.local_mode or self.supabase_configured

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)


@lru_cache
def get_settings() -> Settings:
    return Settings()
