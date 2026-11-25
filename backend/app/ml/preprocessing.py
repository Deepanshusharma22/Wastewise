"""Inference preprocessing — numerically identical to the training eval transform
(torchvision Resize(256, bilinear) -> CenterCrop(224) -> ToTensor -> Normalize),
implemented with Pillow + NumPy so the API does not need PyTorch."""
from __future__ import annotations

import numpy as np
from PIL import Image


def preprocess(img: Image.Image, image_size: int = 224, resize_size: int = 256,
               mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)) -> np.ndarray:
    """RGB PIL image -> float32 array of shape (1, 3, image_size, image_size)."""
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    # torchvision Resize(int): shorter side -> resize_size, keep aspect (floor on the long side)
    if w <= h:
        nw, nh = resize_size, int(resize_size * h / w)
    else:
        nw, nh = int(resize_size * w / h), resize_size
    img = img.resize((nw, nh), Image.BILINEAR)
    left = int(round((nw - image_size) / 2.0))
    top = int(round((nh - image_size) / 2.0))
    img = img.crop((left, top, left + image_size, top + image_size))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    arr = (arr - np.asarray(mean, dtype=np.float32)) / np.asarray(std, dtype=np.float32)
    return arr.transpose(2, 0, 1)[None].astype(np.float32)


def center_crop_view(img: Image.Image, image_size: int = 224, resize_size: int = 256) -> Image.Image:
    """The exact region the model sees (used to overlay the Grad-CAM heatmap)."""
    w, h = img.size
    if w <= h:
        nw, nh = resize_size, int(resize_size * h / w)
    else:
        nw, nh = int(resize_size * w / h), resize_size
    img = img.convert("RGB").resize((nw, nh), Image.BILINEAR)
    left = int(round((nw - image_size) / 2.0))
    top = int(round((nh - image_size) / 2.0))
    return img.crop((left, top, left + image_size, top + image_size))
