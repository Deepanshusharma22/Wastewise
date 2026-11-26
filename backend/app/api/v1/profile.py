"""Profile read/update for the signed-in user.

Uses the same RLS-scoped gateway as everything else, so it works unchanged against
Supabase (RLS on ``profiles``) and in local mode (SQLite). The client uses this
when it cannot talk to Supabase directly (local mode).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...config import Settings, get_settings
from ...database.supabase_client import SupabaseError, SupabaseGateway, pg_eq
from ...utils.security import AuthUser
from ..deps import get_current_user, get_gateway

router = APIRouter(prefix="/profile", tags=["profile"])

_COLUMNS = "id,full_name,email,avatar_url,preferred_language,theme,save_images"


class ProfilePatch(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    preferred_language: str | None = Field(default=None, pattern="^(en|hi)$")
    theme: str | None = Field(default=None, pattern="^(light|dark|system)$")
    save_images: bool | None = None


@router.get("", summary="The caller's profile and preferences")
async def read_profile(user: AuthUser = Depends(get_current_user), gw: SupabaseGateway = Depends(get_gateway),
                      settings: Settings = Depends(get_settings)):
    rows, _ = await gw.select(user.token, "profiles", {"select": _COLUMNS, "id": pg_eq(user.id)})
    if not rows:
        # Local mode creates the row on signup; Supabase uses a trigger. Recover either way.
        try:
            return await gw.insert(user.token, "profiles", {"id": user.id, "email": user.email})
        except SupabaseError:
            raise HTTPException(404, detail={"code": "not_found", "message": "Profile not found."})
    row = dict(rows[0])
    if settings.local_mode and row.get("avatar_url"):
        row["avatar_url_signed"] = (f"{settings.public_base_url}/files/{settings.avatar_bucket}/"
                                    f"{row['avatar_url']}")
    return row


@router.patch("", summary="Update name, language, theme or the save-images privacy setting")
async def update_profile(body: ProfilePatch, user: AuthUser = Depends(get_current_user),
                         gw: SupabaseGateway = Depends(get_gateway), settings: Settings = Depends(get_settings)):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(400, detail={"code": "empty_patch", "message": "Nothing to update."})
    await gw.update(user.token, "profiles", {"id": pg_eq(user.id), "select": "id"}, patch)
    return await read_profile(user=user, gw=gw, settings=settings)
