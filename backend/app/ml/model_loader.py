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


class ModelRegistry:
    """Thread-safe lazy singleton so the app (and serverless cold starts) load the model exactly once."""

    def __init__(self) -> None:
        self._model: LoadedModel | None = None
        self._error: str | None = None
        self._lock = threading.Lock()

    def load(self, model_dir: str) -> LoadedModel | None:
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                import onnxruntime as ort

                d = Path(model_dir)
                card = json.loads((d / "model_card.json").read_text())
                onnx_path = d / "wastewise.onnx"
                digest = hashlib.sha256(onnx_path.read_bytes()).hexdigest()
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
