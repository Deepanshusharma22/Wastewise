"""Image quality heuristics and storage re-encoding."""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

import numpy as np
from PIL import Image, ImageFilter

# Heuristic thresholds. They are advisory only: warnings are shown to the user and stored with the
# prediction, but they never change the model output.
BLUR_LAPLACIAN_VAR = 60.0     # variance of the Laplacian on a 512px greyscale copy
DARK_MEAN = 40.0              # mean luminance (0-255)
BRIGHT_MEAN = 225.0
LOW_RES_SIDE = 160

_MESSAGES = {
    "blurry": {"en": "The photo looks blurry. A sharper photo may give a more reliable result.",
               "hi": "तस्वीर धुंधली लग रही है। स्पष्ट तस्वीर से अधिक विश्वसनीय परिणाम मिल सकता है।"},
    "too_dark": {"en": "The photo is very dark. Try better lighting.",
                 "hi": "तस्वीर बहुत अँधेरी है। बेहतर रोशनी में प्रयास करें।"},
    "too_bright": {"en": "The photo is overexposed. Avoid direct glare or flash.",
                   "hi": "तस्वीर में बहुत अधिक रोशनी है। सीधी चमक या फ़्लैश से बचें।"},
    "low_resolution": {"en": "The image resolution is low. Move closer to the item.",
                       "hi": "तस्वीर का रिज़ॉल्यूशन कम है। वस्तु के पास जाकर फ़ोटो लें।"},
}

_LAPLACE = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128)


def quality_warnings(img: Image.Image) -> list[dict]:
    warnings: list[str] = []
    if min(img.size) < LOW_RES_SIDE:
        warnings.append("low_resolution")
    grey = img.convert("L")
    grey.thumbnail((512, 512))
    arr = np.asarray(grey, dtype=np.float32)
    mean = float(arr.mean())
    if mean < DARK_MEAN:
        warnings.append("too_dark")
    elif mean > BRIGHT_MEAN:
        warnings.append("too_bright")
    lap = np.asarray(grey.filter(_LAPLACE), dtype=np.float32) - 128.0
    if float(lap[1:-1, 1:-1].var()) < BLUR_LAPLACIAN_VAR:
        warnings.append("blurry")
    return [{"code": w, "message": _MESSAGES[w]} for w in warnings]


def encode_for_storage(img: Image.Image, max_side: int, quality: int = 85) -> bytes:
    """Downscale (never upscale) and re-encode as JPEG. Re-encoding also strips EXIF/GPS metadata."""
    out = img.convert("RGB")
    if max(out.size) > max_side:
        out = out.copy()
        out.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue()


def storage_path(user_id: str, prediction_id: str, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    uuid.UUID(prediction_id)  # defensive: only server-generated UUIDs become paths
    return f"{user_id}/{now:%Y}/{now:%m}/{prediction_id}.jpg"
