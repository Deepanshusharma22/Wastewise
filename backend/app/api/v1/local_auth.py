"""Local-mode auth endpoints (signup, confirmation link, resend, login, reset).

Mounted only when ``LOCAL_MODE=1``. Mirrors the shapes the frontend already expects
from Supabase, so the UI code is identical in both modes:

* ``POST /auth/signup``   -> ``{access_token?, user, needs_confirmation, email_link?}``
* ``POST /auth/login``    -> ``{access_token, token_type, expires_in, user}``
* ``POST /auth/confirm``  -> exchange a confirmation-link token for a session
* ``POST /auth/resend``   -> issue a fresh confirmation link (never a dead end)
* ``POST /auth/recover``  -> issue a password-reset link
* ``POST /auth/reset``    -> exchange a reset token for a session
* ``POST /auth/logout``   -> no-op (tokens are stateless)

In local mode there is no external mailer, so the response includes ``email_link``
(the URL that would be emailed) plus ``debug_token``. The UI shows a "continue"
button, which is exactly what the real mail does.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
import re

from pydantic import BaseModel, Field, field_validator

from ...config import Settings, get_settings
from ...database.local_store import LocalStore
from ...utils.local_auth import (TOKEN_PURPOSE_EMAIL, TOKEN_PURPOSE_RESET, issue_access_token, issue_link_token,
                                 parse_link_token, verify_local_token)
from ...utils.rate_limit import client_key, limiter
from ..deps import get_local_store

router = APIRouter(prefix="/auth", tags=["local auth"])

WEB_BASE_URL = "http://localhost:3000"


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


class EmailField(BaseModel):
    """Loose email validation: local demo accounts may use `.local` domains."""

    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def _check(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address.")
        return v.lower()


class SignupIn(EmailField):
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)
    redirect_to: str | None = None


class LoginIn(EmailField):
    password: str = Field(min_length=1, max_length=128)


class TokenIn(BaseModel):
    token: str = Field(min_length=8, max_length=4096)


class EmailIn(EmailField):
    redirect_to: str | None = None


def _link(kind: str, token: str, redirect_to: str | None, settings: Settings) -> str:
    """Build a link that points at the *frontend* callback, exactly like a real mail."""
    base = (redirect_to or WEB_BASE_URL).split("?")[0].rstrip("/")
    return f"{base}/auth/callback?token_hash={token}&type={kind}"


def _require_local(settings: Settings) -> None:
    if not settings.local_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found",
                                                              "message": "Not available."})


@router.post("/signup", status_code=status.HTTP_201_CREATED,
             summary="Create an account (local mode). Returns a session or a confirmation link.")
async def signup(body: SignupIn, request: Request, store: LocalStore = Depends(get_local_store),
                 settings: Settings = Depends(get_settings)):
    _require_local(settings)
    limiter.check("signup:" + client_key(request), [(settings.local_signup_per_hour, 3600)])
    if not (any(c.isalpha() for c in body.password) and any(c.isdigit() for c in body.password)):
        raise HTTPException(422, detail={"code": "weak_password",
                                         "message": "Use at least 8 characters with a letter and a number."})
    if store.get_user_by_email(body.email):
        raise HTTPException(409, detail={"code": "email_taken",
                                         "message": "An account with this email already exists. Try logging in."})
    user = store.create_user(body.email, body.password, body.full_name, confirmed=settings.local_auto_confirm)

    if user["confirmed"]:
        session = issue_access_token(store, user, settings)
        return {"needs_confirmation": False, "email_link": None, "debug_token": None, **session}

    token = issue_link_token(user["email"], TOKEN_PURPOSE_EMAIL, settings)
    return {
        "needs_confirmation": True,
        "user": {"id": user["id"], "email": user["email"]},
        "email_link": _link("email", token, body.redirect_to, settings),
        "debug_token": token,
    }


@router.post("/confirm", summary="Exchange a confirmation link token for a session")
async def confirm(body: TokenIn, store: LocalStore = Depends(get_local_store),
                  settings: Settings = Depends(get_settings)):
    _require_local(settings)
    link = parse_link_token(body.token, TOKEN_PURPOSE_EMAIL, settings)
    if not store.use_link_token(link.nonce):
        raise HTTPException(400, detail={"code": "link_used",
                                         "message": "This link was already used. Request a new one."})
    store.confirm_user(link.email)
    user = store.get_user_by_email(link.email)
    if not user:
        raise HTTPException(404, detail={"code": "not_found", "message": "Account not found."})
    return issue_access_token(store, user, settings)


@router.post("/resend", summary="Send a fresh confirmation link (fixes dead links)")
async def resend(body: EmailIn, request: Request, store: LocalStore = Depends(get_local_store),
                 settings: Settings = Depends(get_settings)):
    _require_local(settings)
    limiter.check("resend:" + client_key(request), [(settings.local_resend_per_5min, 300)])
    user = store.get_user_by_email(body.email)
    # Never reveal whether the address exists.
    if not user:
        return {"sent": True, "email_link": None, "debug_token": None}
    if user["confirmed"]:
        return {"sent": True, "already_confirmed": True, "email_link": None, "debug_token": None}
    token = issue_link_token(user["email"], TOKEN_PURPOSE_EMAIL, settings)
    return {"sent": True, "email_link": _link("email", token, body.redirect_to, settings), "debug_token": token}


@router.post("/login", summary="Email + password login")
async def login(body: LoginIn, request: Request, store: LocalStore = Depends(get_local_store),
                settings: Settings = Depends(get_settings)):
    _require_local(settings)
    limiter.check("login:" + client_key(request), [(settings.local_login_per_5min, 300)])
    user = store.get_user_by_email(body.email)
    if not user or not LocalStore.verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, detail={"code": "invalid_credentials", "message": "Wrong email or password."})
    if not user["confirmed"]:
        raise HTTPException(403, detail={"code": "email_not_confirmed",
                                         "message": "Confirm your email first. You can request a new link below."})
    return issue_access_token(store, user, settings)


@router.post("/recover", summary="Issue a password-reset link")
async def recover(body: EmailIn, request: Request, store: LocalStore = Depends(get_local_store),
                  settings: Settings = Depends(get_settings)):
    _require_local(settings)
    limiter.check("recover:" + client_key(request), [(settings.local_recover_per_hour, 3600)])
    user = store.get_user_by_email(body.email)
    if not user:
        return {"sent": True, "email_link": None, "debug_token": None}
    token = issue_link_token(user["email"], TOKEN_PURPOSE_RESET, settings, ttl_seconds=1800)
    return {"sent": True, "email_link": _link("recovery", token, body.redirect_to, settings), "debug_token": token}


@router.post("/reset", summary="Exchange a reset token, then set the new password")
async def reset(body: TokenIn, store: LocalStore = Depends(get_local_store),
                settings: Settings = Depends(get_settings)):
    _require_local(settings)
    link = parse_link_token(body.token, TOKEN_PURPOSE_RESET, settings)
    if not store.use_link_token(link.nonce):
        raise HTTPException(400, detail={"code": "link_used",
                                         "message": "This link was already used. Request a new one."})
    user = store.get_user_by_email(link.email)
    if not user:
        raise HTTPException(404, detail={"code": "not_found", "message": "Account not found."})
    return issue_access_token(store, user, settings)


class PasswordIn(BaseModel):
    password: str = Field(min_length=8, max_length=128)


@router.post("/password", summary="Set a new password for the logged-in user")
async def set_password(body: PasswordIn, request: Request, store: LocalStore = Depends(get_local_store),
                       settings: Settings = Depends(get_settings)):
    _require_local(settings)
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, detail={"code": "not_authenticated", "message": "Sign in to continue."})
    claims = verify_local_token(settings, auth.split(" ", 1)[1].strip())
    if not (any(c.isalpha() for c in body.password) and any(c.isdigit() for c in body.password)):
        raise HTTPException(422, detail={"code": "weak_password",
                                         "message": "Use at least 8 characters with a letter and a number."})
    store.update_password(claims["sub"], body.password)
    return {"updated": True}


@router.post("/logout", summary="Stateless logout")
async def logout(settings: Settings = Depends(get_settings)):
    _require_local(settings)
    return {"ok": True}


@router.get("/users/{user_id}", summary="Local user lookup (used by the settings screen)")
async def user_info(user_id: str, store: LocalStore = Depends(get_local_store),
                    settings: Settings = Depends(get_settings)):
    _require_local(settings)
    user = store.get_user(user_id)
    if not user:
        raise HTTPException(404, detail={"code": "not_found", "message": "User not found."})
    return {"id": user["id"], "email": user["email"], "full_name": user.get("full_name"),
            "confirmed": bool(user["confirmed"]), "created_at": user["created_at"]}
