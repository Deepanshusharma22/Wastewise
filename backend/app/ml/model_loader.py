"""Loads the exported model once at application startup."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger("wastewise.model")


@dataclass
class LoadedModel:
    session: object               # onnxruntime.InferenceSession
    card: dict
    head: dict[str, np.ndarray]   # Grad-CAM head weights
    path: str

    @property
    def name(self) -> str:
        return self.card["model_name"]

    @property
    def version(self) -> str:
        return self.card["model_version"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def materialise_artifacts(model_dir: Path, base_url: str, card: dict) -> Path:
    """Return a directory containing wastewise.onnx + gradcam_head.npz.

    Normally they are bundled next to model_card.json. Deployments that can only ship text
    files (e.g. Vercel file uploads) set MODEL_BASE_URL to an immutable, commit-pinned URL; the
    binaries are then downloaded once per instance into /tmp and verified against the SHA-256
    recorded in the bundled model card. A mismatch aborts loading.
    """
    if (model_dir / "wastewise.onnx").exists() and (model_dir / "gradcam_head.npz").exists():
        return model_dir
    if not base_url:
        raise FileNotFoundError(f"wastewise.onnx not found in {model_dir} and MODEL_BASE_URL is not set")
    import httpx

    expected = {"wastewise.onnx": card.get("onnx_sha256"), "gradcam_head.npz": card.get("gradcam_head_sha256")}
    if not all(expected.values()):
        raise RuntimeError("model_card.json lacks checksums; refusing to download unverified artifacts")
    cache = Path(os.environ.get("TMPDIR", "/tmp")) / "wastewise-model" / expected["wastewise.onnx"][:16]
    cache.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0), follow_redirects=True) as client:
        for name, digest in expected.items():
            target = cache / name
            if target.exists() and _sha256(target) == digest:
                continue
            tmp = target.with_suffix(target.suffix + ".part")
            with client.stream("GET", f"{base_url.rstrip('/')}/{name}") as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_bytes(1 << 20):
                        f.write(chunk)
            if _sha256(tmp) != digest:
                tmp.unlink(missing_ok=True)
                raise RuntimeError(f"downloaded {name} does not match the checksum in model_card.json")
            tmp.replace(target)
            log.info("downloaded and verified %s", name)
    return cache


# ONNX Runtime sessions are thread-safe for Run(), but Grad-CAM reads the exported head
# plus the feature map from the *same* call; serialising inference keeps latency
# predictable on small instances (2 vCPU) and prevents memory spikes.
inference_lock = threading.Lock()


class ModelRegistry:
    """Thread-safe lazy singleton so the app (and serverless cold starts) load the model exactly once."""

    def __init__(self) -> None:
        self._model: LoadedModel | None = None
        self._error: str | None = None
        self._lock = threading.Lock()

    def load(self, model_dir: str, base_url: str = "") -> LoadedModel | None:
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                import onnxruntime as ort

                card_dir = Path(model_dir)
                card = json.loads((card_dir / "model_card.json").read_text())
                d = materialise_artifacts(card_dir, base_url, card)
                onnx_path = d / "wastewise.onnx"
                digest = _sha256(onnx_path)
                if card.get("onnx_sha256") and card["onnx_sha256"] != digest:
                    raise RuntimeError("model file checksum does not match model_card.json")
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = max(1, min(4, os.cpu_count() or 1))
                opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                sess = ort.InferenceSession(str(onnx_path), sess_options=opts, providers=["CPUExecutionProvider"])
                head = dict(np.load(d / "gradcam_head.npz"))
                self._model = LoadedModel(sess, card, head, str(onnx_path))
                self._error = None
                log.info("model loaded: %s %s", card["model_name"], card["model_version"])
            except Exception as exc:  # surfaced via /health, never swallowed silently
                self._error = f"{type(exc).__name__}: {exc}"
                log.exception("model failed to load")
            return self._model

    @property
    def model(self) -> LoadedModel | None:
        return self._model

    @property
    def error(self) -> str | None:
        return self._error


registry = ModelRegistry()
