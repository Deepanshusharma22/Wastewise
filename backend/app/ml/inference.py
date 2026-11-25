"""Inference + reliability logic + Grad-CAM (pure NumPy, no PyTorch)."""
from __future__ import annotations

import base64
import io
import time
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from .model_loader import LoadedModel
from .preprocessing import center_crop_view, preprocess


@dataclass
class InferenceResult:
    category: str
    confidence: float
    is_confident: bool
    top_predictions: list[dict]
    item: str | None
    item_confidence: float | None
    item_candidates: list[dict]
    probabilities: dict[str, float]
    inference_time_ms: float
    reasons: list[str] = field(default_factory=list)
    features: np.ndarray | None = None      # last conv feature map (C,H,W) for Grad-CAM
    hidden_pre: np.ndarray | None = None


def softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


def _hardswish(x: np.ndarray) -> np.ndarray:
    return x * np.clip(x + 3.0, 0.0, 6.0) / 6.0


def _hardswish_grad(x: np.ndarray) -> np.ndarray:
    return np.where(x < -3.0, 0.0, np.where(x > 3.0, 1.0, (2.0 * x + 3.0) / 6.0))


def predict(model: LoadedModel, img: Image.Image, threshold_override: float | None = None) -> InferenceResult:
    card = model.card
    pp = card["preprocessing"]
    x = preprocess(img, pp["image_size"], pp["resize_size"], tuple(pp["mean"]), tuple(pp["std"]))
    t0 = time.perf_counter()
    feats, cat_logits, item_logits = model.session.run(None, {"image": x})
    elapsed = (time.perf_counter() - t0) * 1000

    categories: list[str] = card["categories"]
    items: list[str] = card["items"]
    T = float(card.get("temperature", 1.0))
    threshold = float(threshold_override if threshold_override is not None else card["confidence_threshold"])

    probs = softmax(cat_logits[0] / T)
    order = np.argsort(-probs)
    top = [{"category": categories[i], "probability": float(probs[i])} for i in order[:3]]
    best = int(order[0])
    conf = float(probs[best])
    category = categories[best]

    reasons: list[str] = []
    if conf < threshold:
        reasons.append("low_confidence")
    margin = float(probs[order[0]] - probs[order[1]])
    if margin < 0.15:
        reasons.append("ambiguous_top2")
    is_confident = conf >= threshold and margin >= 0.15

    # fine-grained item: softmax restricted to the items of the predicted category
    idx = [i for i, it in enumerate(items) if card["item_to_category"][it] == category]
    item, item_conf, cands = None, None, []
    if idx:
        p_items = softmax(item_logits[0][idx] / T)
        o = np.argsort(-p_items)
        cands = [{"item": items[idx[j]], "probability": float(p_items[j])} for j in o[:3]]
        if is_confident and float(p_items[o[0]]) >= float(card.get("item_display_threshold", 0.6)):
            item, item_conf = items[idx[o[0]]], float(p_items[o[0]])

    return InferenceResult(
        category=category, confidence=conf, is_confident=is_confident, top_predictions=top,
        item=item, item_confidence=item_conf, item_candidates=cands,
        probabilities={c: float(p) for c, p in zip(categories, probs)},
        inference_time_ms=round(elapsed, 2), reasons=reasons, features=feats[0],
    )


def gradcam(model: LoadedModel, features: np.ndarray, category: str) -> np.ndarray:
    """Exact Grad-CAM for the head  pool -> Linear(W1) -> Hardswish -> Linear(W2).

    d logit_c / d A_k(i,j) = (1/HW) * sum_h W2[c,h] * hardswish'(z_h) * W1[h,k], identical for
    every spatial position, so the Grad-CAM channel weight alpha_k is that value.
    Returns a (H, W) map in [0, 1].
    """
    head = model.head
    c = model.card["categories"].index(category)
    C, H, W = features.shape
    pooled = features.reshape(C, -1).mean(axis=1)
    z = head["w1"] @ pooled + head["b1"]
    g_hidden = head["w2"][c] * _hardswish_grad(z)
    alpha = (head["w1"].T @ g_hidden) / (H * W)
    cam = np.maximum((alpha[:, None, None] * features).sum(axis=0), 0)
    if cam.max() > 0:
        cam = cam / cam.max()
    return cam.astype(np.float32)


def _colormap(v: np.ndarray) -> np.ndarray:
    """Small perceptual (inferno-like) colormap: values in [0,1] -> RGB uint8."""
    stops = np.array([[0, 0, 4], [87, 16, 110], [188, 55, 84], [249, 142, 9], [252, 255, 164]], dtype=np.float32)
    pos = v * (len(stops) - 1)
    lo = np.clip(np.floor(pos).astype(int), 0, len(stops) - 2)
    frac = (pos - lo)[..., None]
    return (stops[lo] * (1 - frac) + stops[lo + 1] * frac).astype(np.uint8)


def gradcam_overlay_png(model: LoadedModel, img: Image.Image, cam: np.ndarray, alpha: float = 0.45) -> str:
    pp = model.card["preprocessing"]
    base = center_crop_view(img, pp["image_size"], pp["resize_size"])
    heat = Image.fromarray((cam * 255).astype(np.uint8)).resize(base.size, Image.BICUBIC)
    heat_rgb = Image.fromarray(_colormap(np.asarray(heat, dtype=np.float32) / 255.0))
    blended = Image.blend(base, heat_rgb, alpha)
    buf = io.BytesIO()
    blended.save(buf, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
