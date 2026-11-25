"""Reproducible dataset preparation for WasteWise.

Usage:
    python -m ml.src.prepare_data --raw-dir /path/to/raw --out-dir /path/to/processed

Steps
-----
1. Enumerate every source folder declared in ``taxonomy.SOURCE_FOLDERS``.
2. Validate each file (decode + verify) -> corrupted files are reported and skipped.
3. Exact duplicates (MD5) are collapsed; duplicates with conflicting labels are dropped.
4. Near-duplicates (64-bit dHash, Hamming distance <= threshold) are grouped with
   union-find. Groups whose members carry different categories are dropped.
5. Each category is capped at ``--per-category`` images, sampled round-robin across
   its source folders so no single dataset dominates a class.
6. Group-aware stratified split (train/validation/test). All members of a
   near-duplicate group always land in the same split => no leakage.
7. Images are re-encoded (RGB, shorter side 256 px, JPEG q=92) into
   ``out_dir/images/<split>/<category>/<uid>.jpg``.
8. A small out-of-distribution (OOD) probe set is built from categories outside
   the taxonomy (textiles, shoes, mixed trash, paper cups) for threshold calibration.
9. A manifest CSV and a JSON report are written (``ml/datasets/manifests`` and
   ``ml/reports/dataset_report.json``).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from .preprocessing import dhash, load_rgb, md5_file, resize_short_side, verify_image_file
from .taxonomy import CATEGORIES, DATASETS, SOURCE_FOLDERS

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
REPO_ML = Path(__file__).resolve().parents[1]


def _scan_file(args):
    path, = args
    err = verify_image_file(path)
    if err is not None:
        return {"path": path, "error": err}
    img = load_rgb(path)
    gray, color = thumbnail_signature(img)
    return {"path": path, "error": None, "md5": md5_file(path), "dhash": dhash(img),
            "width": img.size[0], "height": img.size[1], "thumb": gray, "color": color}


def _write_processed(args):
    src, dst = args
    img = resize_short_side(load_rgb(src))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    img.save(dst, "JPEG", quality=92)
    return dst


class UnionFind:
    def __init__(self, n: int):
        self.p = list(range(n))

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def thumbnail_signature(img) -> tuple[np.ndarray, np.ndarray]:
    """32x32 grayscale thumbnail (zero-mean, unit-norm) + 4x4 RGB colour layout.

    A 64-bit dHash was tried first but collapses for centred objects on white
    backgrounds (e.g. hash 0c0c0c0c...), chaining thousands of unrelated
    images into one group; normalised thumbnail correlation is far more
    discriminative (see docs/ml_documentation.md, "Duplicate detection").
    """
    from PIL import Image
    g = np.asarray(img.convert("L").resize((32, 32), Image.BILINEAR), dtype=np.float32).flatten()
    g = g - g.mean()
    g = g / (np.linalg.norm(g) + 1e-6)
    c = np.asarray(img.resize((4, 4), Image.BILINEAR), dtype=np.float32).flatten()
    return g.astype(np.float32), c


def near_duplicate_pairs(thumbs: np.ndarray, colors: np.ndarray, threshold: float,
                         max_color_diff: float = 20.0, chunk: int = 1024):
    """Yield (i, j, similarity) pairs (i < j) with thumbnail correlation >= threshold
    and a similar colour layout."""
    n = len(thumbs)
    for start in range(0, n, chunk):
        sim = thumbs[start:start + chunk] @ thumbs.T
        ii, jj = np.nonzero(sim >= threshold)
        for a, b in zip(ii + start, jj):
            if a < b and float(np.abs(colors[a] - colors[b]).mean()) < max_color_diff:
                yield int(a), int(b), float(sim[a - start, b])


def allocate_quota(sizes: dict[str, int], cap: int) -> dict[str, int]:
    """Split ``cap`` across strata as evenly as possible (water-filling)."""
    quota = {k: 0 for k in sizes}
    remaining = min(cap, sum(sizes.values()))
    active = [k for k in sizes if sizes[k] > 0]
    while remaining > 0 and active:
        share = max(1, remaining // len(active))
        for k in list(active):
            take = min(share, sizes[k] - quota[k], remaining)
            quota[k] += take
            remaining -= take
            if quota[k] >= sizes[k]:
                active.remove(k)
            if remaining == 0:
                break
    return quota


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", default=os.environ.get("WASTEWISE_RAW_DIR", str(REPO_ML / "datasets/raw")))
    ap.add_argument("--out-dir", default=os.environ.get("WASTEWISE_DATA_DIR", str(REPO_ML / "datasets/processed")))
    ap.add_argument("--per-category", type=int, default=1100)
    ap.add_argument("--ood-per-folder", type=int, default=60)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--test-frac", type=float, default=0.15)
    ap.add_argument("--group-threshold", type=float, default=0.97,
                    help="thumbnail correlation above which images share a split group (leakage guard)")
    ap.add_argument("--collapse-threshold", type=float, default=0.99,
                    help="thumbnail correlation above which images are treated as duplicates and collapsed")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2)))
    args = ap.parse_args()

    rng = random.Random(args.seed)
    raw, out = Path(args.raw_dir), Path(args.out_dir)
    t0 = time.time()

    # ---------- 1. enumerate ----------
    rows = []
    source_counts = {}
    for sf in SOURCE_FOLDERS:
        folder = raw / sf.rel_path
        if not folder.is_dir():
            raise SystemExit(f"Missing source folder: {folder}. See docs/ml_documentation.md for download steps.")
        files = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMG_EXTS)
        source_counts[sf.rel_path] = len(files)
        if sf.role == "ood":
            files = rng.sample(files, min(len(files), args.ood_per_folder * 3))
        for p in files:
            rows.append({"path": str(p), "dataset": sf.dataset, "stratum": sf.rel_path,
                         "category": sf.category, "item": sf.item, "role": sf.role})
    print(f"[scan] {len(rows)} candidate files from {len(SOURCE_FOLDERS)} folders")

    # ---------- 2. validate + hash ----------
    with ProcessPoolExecutor(args.workers) as ex:
        scanned = list(ex.map(_scan_file, [(r["path"],) for r in rows], chunksize=64))
    by_path = {s["path"]: s for s in scanned}
    corrupted = [{"path": os.path.relpath(s["path"], raw), "error": s["error"]} for s in scanned if s["error"]]
    df = pd.DataFrame([{**r, **by_path[r["path"]]} for r in rows if by_path[r["path"]]["error"] is None])
    print(f"[validate] corrupted/unreadable: {len(corrupted)}  ({time.time()-t0:.0f}s)")

    # ---------- 3. exact duplicates ----------
    df["label_key"] = df["category"].fillna("__ood__")
    exact_conflicts = 0
    keep = []
    exact_dups = 0
    for _, g in df.groupby("md5", sort=False):
        if g["label_key"].nunique() > 1:
            exact_conflicts += len(g)
            continue
        keep.append(g.index[0])
        exact_dups += len(g) - 1
    df = df.loc[sorted(keep)].reset_index(drop=True)
    print(f"[dedupe] exact duplicates removed: {exact_dups}, label-conflicting exact dups dropped: {exact_conflicts}")

    # ---------- 4. near duplicates ----------
    thumbs = np.stack(df["thumb"].to_list())
    colors = np.stack(df["color"].to_list())
    uf_group, uf_dup = UnionFind(len(df)), UnionFind(len(df))
    n_pairs = n_dup_pairs = 0
    for a, b, sim in near_duplicate_pairs(thumbs, colors, args.group_threshold):
        uf_group.union(a, b)
        n_pairs += 1
        if sim >= args.collapse_threshold:
            uf_dup.union(a, b)
            n_dup_pairs += 1
    df["group"] = [uf_group.find(i) for i in range(len(df))]
    df["dup"] = [uf_dup.find(i) for i in range(len(df))]
    group_sizes = df.groupby("group").size()
    multi_groups = int((group_sizes > 1).sum())
    largest_group = int(group_sizes.max())
    nun = df.groupby("group")["label_key"].nunique()
    conflicting_groups = set(nun[nun > 1].index)
    n_conflict_imgs = int(df["group"].isin(conflicting_groups).sum())
    df = df[~df["group"].isin(conflicting_groups)].reset_index(drop=True)
    cross_dataset_groups = int((df.groupby("group")["dataset"].nunique() > 1).sum())
    near_dup_removed = int(len(df) - df["dup"].nunique())
    df = df.drop_duplicates("dup", keep="first").reset_index(drop=True)
    print(f"[near-dup] pairs>={args.group_threshold}: {n_pairs} (>= {args.collapse_threshold}: {n_dup_pairs}), "
          f"multi-image groups: {multi_groups}, largest: {largest_group}, cross-dataset groups: {cross_dataset_groups}, "
          f"label-conflict images dropped: {n_conflict_imgs}, duplicates collapsed: {near_dup_removed}")

    # ---------- 5. capped, stratified sampling ----------
    in_dist = df[df["role"] == "train"]
    sampled_parts = []
    for cat in CATEGORIES:
        cdf = in_dist[in_dist["category"] == cat]
        sizes = cdf.groupby("stratum").size().to_dict()
        quota = allocate_quota(sizes, args.per_category)
        for stratum, q in quota.items():
            sdf = cdf[cdf["stratum"] == stratum]
            sampled_parts.append(sdf.sample(n=q, random_state=args.seed))
    sampled = pd.concat(sampled_parts).reset_index(drop=True)

    # ---------- 6. group-aware stratified split ----------
    # every member of a near-duplicate group goes to the split chosen for the
    # group the first time it is seen -> similar images never straddle splits
    split_of_group: dict[int, str] = {}
    for (_cat, _stratum), sdf in sampled.groupby(["category", "stratum"]):
        groups = list(dict.fromkeys(sdf["group"].tolist()))
        rng.shuffle(groups)
        n = len(groups)
        n_test = max(1, round(n * args.test_frac))
        n_val = max(1, round(n * args.val_frac))
        for i, g in enumerate(groups):
            if g in split_of_group:
                continue
            split_of_group[g] = "test" if i < n_test else ("validation" if i < n_test + n_val else "train")
    sampled["split"] = sampled["group"].map(split_of_group)

    # ---------- 8. OOD probe set ----------
    ood = df[df["role"] == "ood"]
    ood = pd.concat([g.sample(n=min(len(g), args.ood_per_folder), random_state=args.seed)
                     for _, g in ood.groupby("stratum")]) if len(ood) else ood
    ood = ood.assign(split="ood")

    final = pd.concat([sampled, ood]).reset_index(drop=True)
    final["uid"] = [f"{i:05d}" for i in range(len(final))]
    final["file"] = [
        f"images/{r.split}/{r.category if isinstance(r.category, str) else 'ood'}/{r.uid}.jpg"
        for r in final.itertuples()
    ]

    # ---------- 7. write processed images ----------
    with ProcessPoolExecutor(args.workers) as ex:
        list(ex.map(_write_processed, [(r.path, str(out / r.file)) for r in final.itertuples()], chunksize=64))
    print(f"[write] {len(final)} processed images -> {out}  ({time.time()-t0:.0f}s)")

    # ---------- 9. manifest + report ----------
    manifest = final.assign(source_path=[os.path.relpath(p, raw) for p in final["path"]])[
        ["uid", "file", "split", "category", "item", "dataset", "stratum", "source_path", "md5", "dhash",
         "width", "height", "group"]]
    manifest["dhash"] = manifest["dhash"].map(lambda x: f"{int(x):016x}")
    man_dir = REPO_ML / "datasets/manifests"
    man_dir.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(man_dir / "manifest_v1.csv", index=False)
    manifest.to_csv(out / "manifest.csv", index=False)

    split_counts = (sampled.groupby(["category", "split"]).size().unstack(fill_value=0)
                    .reindex(CATEGORIES).reindex(columns=["train", "validation", "test"]))
    cat_avail = in_dist.groupby("category").size().reindex(CATEGORIES).fillna(0).astype(int)
    report = {
        "dataset_version": "v1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "params": vars(args) | {"raw_dir": "<raw>", "out_dir": "<processed>"},
        "sources": DATASETS,
        "raw_folder_counts": source_counts,
        "raw_total_in_taxonomy": int(sum(c for sf, c in zip(SOURCE_FOLDERS, source_counts.values()) if sf.role == "train")),
        "corrupted": corrupted,
        "exact_duplicates_removed": exact_dups,
        "exact_duplicate_label_conflicts_dropped": exact_conflicts,
        "near_duplicate_method": "32x32 grayscale thumbnail correlation + 4x4 colour layout",
        "near_duplicate_pairs": n_pairs,
        "near_duplicate_groups": multi_groups,
        "near_duplicate_largest_group": largest_group,
        "near_duplicate_cross_dataset_groups": cross_dataset_groups,
        "near_duplicate_images_collapsed": near_dup_removed,
        "near_duplicate_label_conflicts_dropped": n_conflict_imgs,
        "available_after_cleaning_per_category": cat_avail.to_dict(),
        "sampled_per_category": sampled.groupby("category").size().reindex(CATEGORIES).to_dict(),
        "split_counts": {c: split_counts.loc[c].to_dict() for c in CATEGORIES},
        "split_totals": sampled.groupby("split").size().to_dict(),
        "per_dataset_per_category": {c: sampled[sampled["category"] == c].groupby("dataset").size().to_dict()
                                     for c in CATEGORIES},
        "item_counts": sampled["item"].value_counts().to_dict(),
        "items_unlabelled": int(sampled["item"].isna().sum()),
        "imbalance_ratio_max_min": float(sampled.groupby("category").size().max()
                                         / sampled.groupby("category").size().min()),
        "ood_counts": ood.groupby("stratum").size().to_dict(),
        "image_size_stats": {"min_side_min": int(np.minimum(sampled.width, sampled.height).min()),
                             "min_side_median": float(np.median(np.minimum(sampled.width, sampled.height)))},
    }
    (REPO_ML / "reports").mkdir(exist_ok=True)
    with open(REPO_ML / "reports/dataset_report.json", "w") as f:
        json.dump(report, f, indent=2, default=lambda o: int(o) if isinstance(o, np.integer) else str(o))
    print(json.dumps({k: report[k] for k in ("sampled_per_category", "split_totals", "imbalance_ratio_max_min")}, indent=1))
    print(f"[done] {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
