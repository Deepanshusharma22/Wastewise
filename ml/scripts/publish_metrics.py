#!/usr/bin/env python3
"""Publish the measured evaluation results into Supabase `model_metrics`.

    SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python ml/scripts/publish_metrics.py

Bug this fixes: `public.model_metrics` had a read policy but **no writer anywhere in the
repo**, so its rows were typed in by hand and could not be reproduced. This script reads
the same artefacts the docs use (`ml/reports/<exp>/evaluation.json`,
`ml/reports/model_comparison.json`, `backend/model_artifacts/model_card.json`) and upserts
one row per experiment, so the table can be rebuilt at any time.

Rows are written with the service-role key because the table is intentionally
read-only for API users (see the migration).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "ml" / "reports"
CARD = REPO / "backend" / "model_artifacts" / "model_card.json"
TEST_DATASET = "wastewise-v1-test"


def collect() -> list[dict]:
    rows: list[dict] = []
    for ev_path in sorted(REPORTS.glob("exp*/evaluation.json")):
        ev = json.loads(ev_path.read_text())
        test = ev.get("test", {})
        rows.append({
            "model_name": ev.get("arch", ev_path.parent.name),
            "model_version": f"1.0.0-{ev.get('arch', 'unknown')}",
            "accuracy": test.get("accuracy"),
            "precision_macro": test.get("precision_macro"),
            "recall_macro": test.get("recall_macro"),
            "f1_macro": test.get("f1_macro"),
            "test_dataset": TEST_DATASET,
            "details": {
                "experiment_id": ev.get("experiment_id"),
                "roc_auc_ovr_macro": test.get("roc_auc_ovr_macro"),
                "confidence_threshold": ev.get("confidence_threshold"),
                "temperature": ev.get("temperature"),
                "coverage_at_threshold": (ev.get("test_selective") or {}).get("coverage"),
                "accuracy_on_accepted": (ev.get("test_selective") or {}).get("accuracy_on_accepted"),
                "ood_rejection_rate": (ev.get("ood") or {}).get("rejection_rate"),
                "ood_images": (ev.get("ood") or {}).get("n"),
                "per_class": test.get("per_class"),
                "test_images": len(json.loads((REPO / "ml/datasets/manifests/manifest_v1.csv").read_text()).splitlines()) - 1
                if False else (ev.get("test_selective") or {}).get("n"),
                "source": str(ev_path.relative_to(REPO)),
            },
        })
    if not rows:
        raise SystemExit("no evaluation.json files found - run ml/src/evaluate.py first")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print the rows instead of writing them")
    args = ap.parse_args()

    rows = collect()
    if CARD.exists():
        card = json.loads(CARD.read_text())
        for r in rows:
            r["details"]["selected"] = r["model_version"].endswith(card.get("architecture", ""))

    if args.dry_run:
        print(json.dumps(rows, indent=2))
        return 0

    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required (service role writes this table).")
        return 1

    import httpx

    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "resolution=merge-duplicates,return=representation",
               "Content-Type": "application/json"}
    with httpx.Client(timeout=30) as client:
        for row in rows:
            res = client.post(f"{url}/rest/v1/model_metrics?on_conflict=model_name,model_version,test_dataset",
                              headers=headers, json=row)
            res.raise_for_status()
            print(f"published {row['model_version']} ({row['test_dataset']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
