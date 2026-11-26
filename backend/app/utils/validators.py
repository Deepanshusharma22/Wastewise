"""Upload validation: size, declared MIME type, magic bytes and real decodability."""
from __future__ import annotations

import io
import re
import uuid

from PIL import Image, ImageOps

ALLOWED_MIME = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


class ValidationFailure(ValueError):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def sniff_image_type(data: bytes) -> str | None:
    """Identify the real file type from its magic bytes (never trust the client's Content-Type)."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_image_bytes(data: bytes, declared_type: str | None, max_bytes: int, max_pixels: int,
                         min_side: int = 64) -> Image.Image:
    if not data:
        raise ValidationFailure("empty_file", "The uploaded file is empty.")
    if len(data) > max_bytes:
        raise ValidationFailure("file_too_large", f"Image exceeds the {max_bytes // (1024 * 1024)} MB limit.", 413)
    if declared_type and declared_type.lower() not in ALLOWED_MIME:
        raise ValidationFailure("unsupported_type", "Only JPG, PNG and WEBP images are supported.", 415)
    real = sniff_image_type(data)
    if real is None:
        raise ValidationFailure("unsupported_type", "File content is not a JPG, PNG or WEBP image.", 415)
    Image.MAX_IMAGE_PIXELS = max_pixels
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        img = Image.open(io.BytesIO(data))
        if img.width * img.height > max_pixels:
            raise ValidationFailure("image_too_large", "Image resolution is too large.", 413)
        img.load()
    except ValidationFailure:
        raise
    except Exception:
        raise ValidationFailure("corrupt_image", "The image could not be decoded. It may be corrupted.")
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    if min(img.size) < min_side:
        raise ValidationFailure("image_too_small", f"Image must be at least {min_side}x{min_side} pixels.")
    return img


_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def is_uuid(value: str) -> bool:
    if not _UUID_RE.match(value or ""):
        return False
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


# Prediction images:   <user_id>/<yyyy>/<mm>/<prediction-uuid>.jpg
# Avatars:             <user_id>/avatar-<8 hex>.<jpg|png|webp>
_PREDICTION_PATH = r"\d{4}/\d{2}/[0-9a-f\-]{36}\.jpg"
_AVATAR_PATH = r"avatar-[0-9a-f]{8}\.(?:jpg|png|webp)"
_AVATAR_EXT = {"image/png": "png", "image/webp": "webp"}


def avatar_storage_path(user_id: str, uploaded_file, force_new: bool = False) -> str:
    """Server-generated avatar object path: `<user_id>/avatar-<8 hex>.<ext>`.

    The random suffix is what the storage-path validator and the bucket policies expect,
    and it doubles as a cache-buster when the user replaces their photo. Any previously
    returned path for the same user is cleaned up by the caller.
    """
    ext = _AVATAR_EXT.get((getattr(uploaded_file, "content_type", "") or "").lower(), "jpg")
    suffix = uuid.uuid4().hex[:8]
    return f"{user_id}/avatar-{suffix}.{ext}"


def is_owned_storage_path(path: str | None, user_id: str) -> bool:
    """Storage paths are generated server-side; double-check before using them.

    Accepts only the two shapes the app itself writes (see ``image_service.storage_path``
    and the avatar upload in Settings). Anything else — including a path with ``..`` —
    is rejected, so a tampered row can never point at another user's object.
    """
    if not path or ".." in path:
        return False
    stem = rf"{re.escape(user_id)}/"
    return bool(re.fullmatch(stem + _PREDICTION_PATH, path) or re.fullmatch(stem + _AVATAR_PATH, path))
