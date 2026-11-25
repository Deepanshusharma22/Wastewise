"""Checks against the REAL exported artefacts in backend/model_artifacts (skipped until select_model.py ran)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

ART = Path(__file__).resolve().parents[1] / "model_artifacts"
pytestmark = pytest.mark.skipif(not (ART / "wastewise.onnx").exists(), reason="model not exported yet")


def test_card_checksum_and_contract():
    card = json.loads((ART / "model_card.json").read_text())
    assert hashlib.sha256((ART / "wastewise.onnx").read_bytes()).hexdigest() == card["onnx_sha256"]
    assert len(card["categories"]) == 7 and 0 < card["confidence_threshold"] < 1 and card["temperature"] > 0
    assert set(card["item_to_category"].values()) <= set(card["categories"])
    for k in ("test_accuracy", "test_f1_macro", "test_images"):
        assert k in card["metrics"]


def test_gradcam_head_matches_onnx_logits():
    """The NumPy head used for Grad-CAM must reproduce the exported graph exactly (dropout is identity at eval)."""
    from app.ml import inference
    from app.ml.model_loader import ModelRegistry
    m = ModelRegistry().load(str(ART))
    assert m is not None
    rng = np.random.default_rng(0)
    x = rng.standard_normal((1, 3, 224, 224)).astype(np.float32)
    feats, cat_logits, _ = m.session.run(None, {"image": x})
    f = feats[0].astype(np.float64)
    pooled = f.reshape(f.shape[0], -1).mean(axis=1)
    z = m.head["w1"] @ pooled + m.head["b1"]
    h = z * np.clip(z + 3, 0, 6) / 6
    logits = m.head["w2"] @ h + m.head["b2"]
    np.testing.assert_allclose(logits, cat_logits[0], rtol=1e-3, atol=1e-3)
    cam = inference.gradcam(m, feats[0], m.card["categories"][int(np.argmax(cat_logits[0]))])
    assert cam.ndim == 2 and np.isfinite(cam).all()
