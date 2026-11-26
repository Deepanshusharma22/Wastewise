"""File serving for local mode (stands in for Supabase Storage signed URLs).

Only mounted when ``LOCAL_MODE=1``. Access is checked against the caller's JWT: a
user may only read objects under their own ``<user_id>/`` prefix, which mirrors the
private-bucket storage policies. Images are served with ``Cache-Control: private``.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ...config import Settings, get_settings
from ...utils.security import AuthUser
from ..deps import get_current_user

router = APIRouter(tags=["local files"])


@router.get("/files/{bucket}/{path:path}", include_in_schema=False)
async def serve_file(bucket: str, path: str, user: AuthUser = Depends(get_current_user),
                     settings: Settings = Depends(get_settings)):
    if bucket not in (settings.storage_bucket, settings.avatar_bucket):
        raise HTTPException(404, detail={"code": "not_found", "message": "Not found."})
    safe = Path(path)
    if safe.is_absolute() or ".." in safe.parts:
        raise HTTPException(400, detail={"code": "bad_path", "message": "Invalid path."})
    # object paths are always `<user_id>/...` — same rule as the storage policies
    if safe.parts[0] != user.id:
        raise HTTPException(403, detail={"code": "forbidden", "message": "You are not allowed to access this file."})
    target = Path(settings.local_storage_dir) / bucket / safe
    if not target.is_file():
        raise HTTPException(404, detail={"code": "not_found", "message": "File not found."})
    return FileResponse(target, headers={"Cache-Control": "private, max-age=300"})
