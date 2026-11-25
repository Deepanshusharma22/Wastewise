"""Unit tests for ML evaluation helpers (synthetic data only — no model or dataset required).

    python -m pytest ml/tests -q
"""
from __future__ import annotations

import numpy as np
import pytest
import torch

from ml.src import evaluate as ev
from ml.src.metrics import (classification_metrics, expected_calibration_error, fit_temperature,
                            selective_curve)
from ml.src.taxonomy import CATEGORIES, ITEM_TO_CATEGORY, ITEMS


def _probs(n=400, k=7, sharp=4.0, acc=0.85, seed=0):
    rng = np.random.default_rng(seed)
    y = rng.integers(0, k, n)
    pred = np.where(rng.random(n) < acc, y, rng.integers(0, k, n))
    logits = rng.normal(0, 1, (n, k))
    logits[np.arange(n), pred] += sharp
    p = np.exp(logits)
    return p / p.sum(1, keepdims=True), y


def test_taxonomy_consistent():
    assert len(CATEGORIES) == 7
    assert set(ITEM_TO_CATEGORY.values()) <= set(CATEGORIES)
    assert all(i in ITEM_TO_CATEGORY for i in ITEMS)


def test_classification_metrics_perfect():
    y = np.repeat(np.arange(7), 5)
    p = np.eye(7)[y] * 0.9 + 0.1 / 7
    m = classification_metrics(y, p, CATEGORIES)
    assert m["accuracy"] == 1.0 and m["f1_macro"] == 1.0
    assert m["roc_auc_ovr_macro"] == pytest.approx(1.0)
    assert np.trace(np.array(m["confusion_matrix"])) == len(y)


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_classification_metrics_missing_class_does_not_crash():
    y = np.array([0, 0, 1, 1])
    p = np.eye(7)[y]
    m = classification_metrics(y, p, CATEGORIES)
    assert len(m["confusion_matrix"]) == 7
    assert m["roc_auc_ovr_macro"] is None  # undefined when classes are absent


def test_selective_curve_monotone_coverage():
    p, y = _probs()
    curve = selective_curve(p, y, np.linspace(0.3, 0.95, 14))
    cov = [r["coverage"] for r in curve]
    assert all(a >= b for a, b in zip(cov, cov[1:]))


def test_choose_threshold_meets_target_or_falls_back():
    p, y = _probs(acc=0.85)
    t, curve = ev.choose_threshold(p, y)
    lo, hi = ev.THRESHOLD_BOUNDS
    row = next(r for r in curve if r["threshold"] == t)
    if t != ev.DEFAULT_THRESHOLD:
        assert lo <= t <= hi and row["selective_accuracy"] >= ev.TARGET_SELECTIVE_ACC
    # a model that is pure noise can never reach the target -> documented fallback
    rng = np.random.default_rng(1)
    noise = rng.dirichlet(np.ones(7), 300)
    t2, _ = ev.choose_threshold(noise, rng.integers(0, 7, 300))
    assert t2 == ev.DEFAULT_THRESHOLD


def test_fit_temperature_reduces_overconfidence():
    torch.manual_seed(0)
    n = 2000
    y = torch.randint(0, 7, (n,))
    logits = torch.randn(n, 7)
    correct = torch.rand(n) < 0.7
    target = torch.where(correct, y, torch.randint(0, 7, (n,)))
    logits[torch.arange(n), target] += 3.0
    logits = logits * 4.0  # make it badly over-confident
    T = fit_temperature(logits, y)
    assert T > 1.5
    before = expected_calibration_error(torch.softmax(logits, 1).numpy(), y.numpy())
    after = expected_calibration_error(torch.softmax(logits / T, 1).numpy(), y.numpy())
    assert after < before


def test_plots_write_files(tmp_path):
    p, y = _probs()
    m = classification_metrics(y, p, CATEGORIES)
    ev.plot_confusion(np.array(m["confusion_matrix"]), CATEGORIES, tmp_path / "cm.png", "t")
    t, curve = ev.choose_threshold(p, y)
    ev.plot_selective(curve, p.max(1)[:50], t, tmp_path / "sel.png")
    assert (tmp_path / "cm.png").stat().st_size > 1000
    assert (tmp_path / "sel.png").stat().st_size > 1000
