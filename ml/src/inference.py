"""PyTorch reference inference (research / notebooks / parity tests).

    python -m ml.src.inference path/to/image.jpg [--checkpoint ml/models/best_model.pth] [--gradcam out.jpg]

The production API does NOT import this module: it runs the exported ONNX graph
with onnxruntime (``backend/app/ml``). ``backend/tests`` compare both paths on
the same image to guarantee they agree.

Behaviour
  * Top-3 category predictions with temperature-scaled probabilities.
  * A prediction is "confident" only if p_top1 >= threshold AND p_top1 - p_top2 >= 0.15.
    Otherwise the caller must show LOW_CONFIDENCE_MESSAGE instead of forcing a label.
  * Grad-CAM over the last convolutional stage.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from .augmentation import eval_transforms
from .evaluate import load_checkpoint
from .preprocessing import load_rgb

LOW_CONFIDENCE_MESSAGE = "Unable to confidently identify this waste item. Please upload a clearer image."
MIN_TOP2_MARGIN = 0.15
DEFAULT_THRESHOLD = 0.65


@dataclass
class Prediction:
    category: str
    confidence: float
    is_confident: bool
    message: str | None
    top3: list[dict]
    item: str | None
    item_confidence: float | None


class WastePredictor:
    def __init__(self, checkpoint: str = "ml/models/best_model.pth", threshold: float | None = None):
        self.model, ck = load_checkpoint(checkpoint)
        self.categories: list[str] = ck["categories"]
        self.items: list[str] = ck["items"]
        self.item_to_category: dict[str, str] = ck["item_to_category"]
        self.temperature = float(ck.get("temperature", 1.0))
        self.threshold = float(threshold if threshold is not None else ck.get("confidence_threshold", DEFAULT_THRESHOLD))
        self.item_threshold = 0.6
        pp = ck.get("preprocessing", {})
        self.tf = eval_transforms(pp.get("image_size", 224), pp.get("resize_size", 256))

    def _tensor(self, img: Image.Image) -> torch.Tensor:
        return self.tf(img.convert("RGB")).unsqueeze(0)

    @torch.no_grad()
    def predict(self, image: str | bytes | Image.Image) -> Prediction:
        img = image if isinstance(image, Image.Image) else load_rgb(image)
        cat_logits, item_logits = self.model(self._tensor(img))
        probs = F.softmax(cat_logits[0] / self.temperature, dim=0).numpy()
        order = np.argsort(-probs)
        top3 = [{"category": self.categories[i], "probability": float(probs[i])} for i in order[:3]]
        conf = float(probs[order[0]])
        category = self.categories[order[0]]
        confident = conf >= self.threshold and conf - float(probs[order[1]]) >= MIN_TOP2_MARGIN

        item, item_conf = None, None
        idx = [i for i, it in enumerate(self.items) if self.item_to_category[it] == category]
        if confident and idx:
            p = F.softmax(item_logits[0, idx] / self.temperature, dim=0).numpy()
            j = int(np.argmax(p))
            if p[j] >= self.item_threshold:
                item, item_conf = self.items[idx[j]], float(p[j])
        return Prediction(category, conf, confident, None if confident else LOW_CONFIDENCE_MESSAGE,
                          top3, item, item_conf)

    def gradcam(self, image: str | bytes | Image.Image, category: str | None = None) -> np.ndarray:
        """Standard Grad-CAM (Selvaraju et al. 2017) on ``model.gradcam_layer``; returns (H, W) in [0, 1]."""
        img = image if isinstance(image, Image.Image) else load_rgb(image)
        store: dict[str, torch.Tensor] = {}
        layer = self.model.gradcam_layer
        h1 = layer.register_forward_hook(lambda m, i, o: store.__setitem__("act", o))
        h2 = layer.register_full_backward_hook(lambda m, gi, go: store.__setitem__("grad", go[0]))
        try:
            x = self._tensor(img).requires_grad_(True)
            logits, _ = self.model(x)
            c = self.categories.index(category) if category else int(logits[0].argmax())
            self.model.zero_grad()
            logits[0, c].backward()
        finally:
            h1.remove()
            h2.remove()
        act, grad = store["act"][0], store["grad"][0]
        weights = grad.mean(dim=(1, 2))
        cam = F.relu((weights[:, None, None] * act).sum(0)).detach().numpy()
        return cam / cam.max() if cam.max() > 0 else cam


def overlay(img: Image.Image, cam: np.ndarray, size: int = 224, alpha: float = 0.45) -> Image.Image:
    import matplotlib.cm as cm

    base = eval_transforms(size).transforms[0](img.convert("RGB"))
    base = eval_transforms(size).transforms[1](base)
    heat = Image.fromarray((cam * 255).astype(np.uint8)).resize(base.size, Image.BICUBIC)
    rgb = (cm.inferno(np.asarray(heat) / 255.0)[..., :3] * 255).astype(np.uint8)
    return Image.blend(base, Image.fromarray(rgb), alpha)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--checkpoint", default="ml/models/best_model.pth")
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--gradcam", default=None, help="write a Grad-CAM overlay JPEG here")
    a = ap.parse_args()
    p = WastePredictor(a.checkpoint, a.threshold)
    pred = p.predict(a.image)
    print(json.dumps(asdict(pred), indent=2))
    if a.gradcam:
        img = load_rgb(a.image)
        overlay(img, p.gradcam(img, pred.category)).save(a.gradcam, quality=90)
        print(f"grad-cam -> {a.gradcam}")


if __name__ == "__main__":
    main()
