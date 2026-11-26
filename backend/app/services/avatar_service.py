"""Avatar upload/removal (works in both Supabase and local mode)."""
from __future__ import annotations

import logging

from ..config import Settings
from ..database.supabase_client import SupabaseError, SupabaseGateway, pg_eq
from ..utils.security import AuthUser
from ..utils.validators import avatar_storage_path, is_owned_storage_path

log = logging.getLogger("wastewise.avatar")


async def replace_avatar(gw: SupabaseGateway, settings: Settings, user: AuthUser, data: bytes,
                         content_type: str) -> str:
    from ..database.local_store import LocalStore

    path = avatar_storage_path(user.id, type("F", (), {"content_type": content_type})(), force_new=True)
    await gw.upload(user.token, settings.avatar_bucket, path, data, content_type, upsert=True)
    rows, _ = await gw.select(user.token, "profiles", {"select": "avatar_url", "id": pg_eq(user.id)})
    previous = rows[0].get("avatar_url") if rows else None
    await gw.update(user.token, "profiles", {"id": pg_eq(user.id), "select": "id"}, {"avatar_url": path})
    if previous and previous != path and is_owned_storage_path(previous, user.id):
        try:
            await gw.remove(user.token, settings.avatar_bucket, [previous])
        except SupabaseError:
            log.warning("could not remove previous avatar %s", previous)
    if isinstance(gw, LocalStore):
        # local mode: hand back a directly usable URL (Supabase uses signed URLs client-side)
        return path
    return path
