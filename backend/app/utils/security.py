"""Supabase JWT verification.

Supports projects using asymmetric signing keys (ES256/RS256, verified through the
project's JWKS endpoint or a static JWKS) and legacy HS256 projects (shared secret).
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWK, PyJWKClient

from ..config import Settings, get_settings
from .validators import is_uuid

log = logging.getLogger("wastewise.auth")
bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str | None
    token: str
    role: str


class JWTVerifier:
    def __init__(self, settings: Settings):
        self.s = settings
        self._static: dict[str, PyJWK] = {}
        self._client: PyJWKClient | None = None
        if settings.supabase_jwks:
            for k in json.loads(settings.supabase_jwks)["keys"]:
                jwk = PyJWK(k)
                self._static[k.get("kid", "")] = jwk
        elif settings.supabase_url:
            self._client = PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json",
                                       cache_jwk_set=True, lifespan=600, timeout=5)

    def _key_for(self, token: str, header: dict):
        alg = header.get("alg")
        if alg == "HS256":
            if not self.s.supabase_jwt_secret:
                raise jwt.InvalidTokenError("HS256 tokens not accepted (no secret configured)")
            return self.s.supabase_jwt_secret, ["HS256"]
        if alg not in ("ES256", "RS256", "EdDSA"):
            raise jwt.InvalidTokenError(f"unsupported alg {alg}")
        kid = header.get("kid", "")
        if self._static:
            jwk = self._static.get(kid) or (next(iter(self._static.values())) if len(self._static) == 1 else None)
            if jwk is None:
                raise jwt.InvalidTokenError("unknown signing key")
            return jwk.key, [alg]
        if self._client is None:
            raise jwt.InvalidTokenError("no JWKS source configured")
        return self._client.get_signing_key_from_jwt(token).key, [alg]

    def verify(self, token: str) -> AuthUser:
        header = jwt.get_unverified_header(token)
        key, algs = self._key_for(token, header)
        claims = jwt.decode(
            token, key, algorithms=algs, audience="authenticated",
            issuer=f"{self.s.supabase_url}/auth/v1" if self.s.supabase_url else None,
            options={"require": ["exp", "sub", "aud"], "verify_iss": bool(self.s.supabase_url)},
            leeway=10,
        )
        if claims.get("role") != "authenticated" or not is_uuid(claims.get("sub", "")):
            raise jwt.InvalidTokenError("not an authenticated user token")
        return AuthUser(id=claims["sub"], email=claims.get("email"), token=token, role=claims["role"])


_verifier: JWTVerifier | None = None
_verifier_built_at = 0.0


def get_verifier(settings: Settings = Depends(get_settings)) -> JWTVerifier:
    global _verifier, _verifier_built_at
    if _verifier is None or _verifier.s is not settings:
        _verifier, _verifier_built_at = JWTVerifier(settings), time.time()
    return _verifier


def authenticate_bearer(request: Request, creds: HTTPAuthorizationCredentials | None,
                        verifier: JWTVerifier) -> AuthUser:
    """Verify a Supabase bearer token (shared by the plain dependency and the mode-aware one)."""
    if creds is None or creds.scheme.lower() != "bearer" or not creds.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "not_authenticated",
                                                                   "message": "Sign in to continue."},
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        user = verifier.verify(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "token_expired",
                                                                   "message": "Your session has expired. Please sign in again."})
    except Exception as exc:
        log.info("rejected token: %s", type(exc).__name__)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "invalid_token",
                                                                   "message": "Invalid authentication token."})
    request.state.user_id = user.id
    return user


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    verifier: JWTVerifier = Depends(get_verifier),
) -> AuthUser:
    return authenticate_bearer(request, creds, verifier)
