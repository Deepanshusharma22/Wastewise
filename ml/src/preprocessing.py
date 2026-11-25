"""Image preprocessing utilities shared by data preparation, training and inference.

The constants here MUST stay identical to ``backend/app/ml/preprocessing.py``;
``backend/tests/test_ml_inference.py`` checks that the deployed checkpoint's
embedded preprocessing config matches the backend implementation.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps

IMAGE_SIZE = 224          # network input resolution
RESIZE_SIZE = 256         # shorter side before the centre crop at eval time
PROCESSED_SHORT_SIDE = 256  # shorter side of images written to datasets/processed
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
MIN_IMAGE_SIDE = 32


class InvalidImageError(ValueError):
    """Raised when a file cannot be decoded as a usable image."""


def load_rgb(source: str | bytes | io.BytesIO) -> Image.Image:
    """Decode an image, apply EXIF orientation and convert to RGB.

    Transparent images are composited on a white background (EWasteNet PNGs
    are RGBA cut-outs) so alpha doesn't turn into black backgrounds.
    """
    try:
        if isinstance(source, bytes):
            source = io.BytesIO(source)
        img = Image.open(source)
        img.load()
    except Exception as exc:  # PIL raises many exception types
        raise InvalidImageError(f"cannot decode image: {exc}") from exc
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    if min(img.size) < MIN_IMAGE_SIDE:
        raise InvalidImageError(f"image too small: {img.size}")
    return img


def verify_image_file(path: str) -> str | None:
    """Return None if the file is a valid image, otherwise an error string."""
    try:
        with Image.open(path) as im:
            im.verify()
        load_rgb(path)
        return None
    except Exception as exc:
        return str(exc)


def resize_short_side(img: Image.Image, short_side: int = PROCESSED_SHORT_SIDE) -> Image.Image:
    w, h = img.size
    s = min(w, h)
    if s <= short_side:
        return img
    scale = short_side / s
    return img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.BICUBIC)


def md5_file(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dhash(img: Image.Image, hash_size: int = 8) -> int:
    """64-bit difference hash, robust to resizing/re-encoding (near-duplicate detection)."""
    g = img.convert("L").resize((hash_size + 1, hash_size), Image.BILINEAR)
    a = np.asarray(g, dtype=np.int16)
    bits = (a[:, 1:] > a[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


@dataclass
class QualityReport:
    brightness: float
    contrast: float
    sharpness: float
    warnings: list[str]


def image_quality(img: Image.Image) -> QualityReport:
    """Cheap heuristics to flag images that are unlikely to give reliable predictions."""
    g = np.asarray(img.convert("L").resize((256, 256)), dtype=np.float32)
    brightness = float(g.mean())
    contrast = float(g.std())
    # variance of a 4-neighbour Laplacian = focus measure
    lap = (-4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:])
    sharpness = float(lap.var())
    warnings: list[str] = []
    if brightness < 30:
        warnings.append("too_dark")
    elif brightness > 235:
        warnings.append("too_bright")
    if contrast < 12:
        warnings.append("low_contrast")
    if sharpness < 15:
        warnings.append("blurry")
    return QualityReport(brightness, contrast, sharpness, warnings)
