"""Local-mode authentication: signed JWTs + single-use email-link tokens.

Only active when ``LOCAL_MODE=1``. It exists so the whole product (signup with a
confirmation link, login, password reset, account deletion) can be exercised
end-to-end without a Supabase project. It is **not** a replacement for Supabase Auth:
passwords are PBKDF2-hashed, tokens are HS256 and short-lived, and every link token
is single-use, exactly like a real confirmation flow.
"""
from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass

import jwt
from fastapi import HTTPException, status

from ..config import Settings
from ..database.local_store import LocalStore

TOKEN_PURPOSE_EMAIL = "email"
TOKEN_PURPOSE_RESET = "reset"


def issue_access_token(store: LocalStore, user: dict, settings: Settings) -> dict:
    now = int(time.time())
    expires = now + settings.local_token_ttl_seconds
    claims = {
        "sub": user["id"],
        "aud": "authenticated",
        "role": "authenticated",
        "email": user["email"],
        "iss": "wastewise-local",
        "iat": now,
        "exp": expires,
    }
    token = jwt.encode(claims, settings.local_jwt_secret, algorithm="HS256")
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.local_token_ttl_seconds,
        "expires_at": expires,
        "user": {"id": user["id"], "email": user["email"], "full_name": user.get("full_name")},
    }


def verify_local_token(settings: Settings, token: str) -> dict:
    try:
        claims = jwt.decode(token, settings.local_jwt_secret, algorithms=["HS256"],
                            audience="authenticated", issuer="wastewise-local",
                            options={"require": ["exp", "sub", "aud"]}, leeway=10)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "token_expired",
                                                                  "message": "Your session has expired. Please sign in again."})
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "invalid_token",
                                                                  "message": "Invalid authentication token."})
    if claims.get("role") != "authenticated":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "invalid_token",
                                                                  "message": "Invalid authentication token."})
    return claims


# ---------------------------------------------------------------------- link tokens
def _link_signature(secret: str, payload: str) -> str:
    return hashlib.sha256(f"{secret}:{payload}".encode()).hexdigest()[:32]


def issue_link_token(email: str, purpose: str, settings: Settings, ttl_seconds: int = 3600) -> str:
    payload = f"{email.lower()}|{purpose}|{int(time.time()) + ttl_seconds}|{secrets.token_hex(8)}"
    return f"{payload}|{_link_signature(settings.local_jwt_secret, payload)}"


@dataclass(frozen=True)
class LinkToken:
    email: str
    purpose: str
    expires_at: int
    nonce: str


def parse_link_token(token: str, expected_purpose: str, settings: Settings) -> LinkToken:
    parts = (token or "").split("|")
    if len(parts) != 5:
        raise _bad_link()
    email, purpose, expiry, nonce, signature = parts
    payload = f"{email}|{purpose}|{expiry}|{nonce}"
    if not secrets.compare_digest(signature, _link_signature(settings.local_jwt_secret, payload)):
        raise _bad_link()
    if purpose != expected_purpose:
        raise _bad_link()
    try:
        expires_at = int(expiry)
    except ValueError:
        raise _bad_link()
    if time.time() > expires_at:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            detail={"code": "link_expired",
                                    "message": "This link has expired. Request a new one and try again."})
    return LinkToken(email=email, purpose=purpose, expires_at=expires_at, nonce=nonce)


def _bad_link() -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST,
                         detail={"code": "invalid_link",
                                 "message": "This link is invalid or has already been used. Request a new one."})
