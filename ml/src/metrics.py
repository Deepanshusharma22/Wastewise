"""Evaluation metrics helpers."""
from __future__ import annotations

import numpy as np
import torch
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)


def classification_metrics(y_true: np.ndarray, probs: np.ndarray, labels: list[str]) -> dict:
    y_pred = probs.argmax(1)
    idx = list(range(len(labels)))
    out = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_macro": float(precision_score(y_true, y_pred, average="macro", labels=idx, zero_division=0)),
        "recall_macro": float(recall_score(y_true, y_pred, average="macro", labels=idx, zero_division=0)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", labels=idx, zero_division=0)),
        "precision_weighted": float(precision_score(y_true, y_pred, average="weighted", labels=idx, zero_division=0)),
        "recall_weighted": float(recall_score(y_true, y_pred, average="weighted", labels=idx, zero_division=0)),
        "f1_weighted": float(f1_score(y_true, y_pred, average="weighted", labels=idx, zero_division=0)),
        "per_class": classification_report(y_true, y_pred, labels=idx, target_names=labels,
                                           output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=idx).tolist(),
    }
    try:
        auc = float(roc_auc_score(y_true, probs, multi_class="ovr", average="macro", labels=idx))
        out["roc_auc_ovr_macro"] = auc if np.isfinite(auc) else None  # NaN when a class is absent
    except ValueError:
        out["roc_auc_ovr_macro"] = None
    return out


def expected_calibration_error(probs: np.ndarray, y_true: np.ndarray, n_bins: int = 15) -> float:
    conf = probs.max(1)
    correct = probs.argmax(1) == y_true
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            ece += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(ece)


def fit_temperature(logits: torch.Tensor, labels: torch.Tensor) -> float:
    """Temperature scaling (Guo et al., 2017) fitted on validation logits by NLL minimisation."""
    log_t = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.05, max_iter=200)
    nll = torch.nn.CrossEntropyLoss()

    def closure():
        opt.zero_grad()
        loss = nll(logits / log_t.exp(), labels)
        loss.backward()
        return loss

    opt.step(closure)
    return float(log_t.exp().clamp(0.05, 20).item())


def selective_curve(probs: np.ndarray, y_true: np.ndarray, thresholds: np.ndarray) -> list[dict]:
    conf = probs.max(1)
    correct = probs.argmax(1) == y_true
    rows = []
    for t in thresholds:
        acc_mask = conf >= t
        rows.append({
            "threshold": float(t),
            "coverage": float(acc_mask.mean()),
            "selective_accuracy": float(correct[acc_mask].mean()) if acc_mask.any() else None,
        })
    return rows
