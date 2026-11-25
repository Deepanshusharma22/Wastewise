"""PyTorch datasets / loaders built from the prepared manifest."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset

from .augmentation import eval_transforms, train_transforms
from .preprocessing import load_rgb
from .taxonomy import CATEGORIES, ITEMS

IGNORE_INDEX = -100


class WasteDataset(Dataset):
    def __init__(self, data_dir: str, manifest: pd.DataFrame, split: str, transform):
        self.data_dir = data_dir
        self.df = manifest[manifest["split"] == split].reset_index(drop=True)
        self.transform = transform
        self.cat_idx = {c: i for i, c in enumerate(CATEGORIES)}
        self.item_idx = {c: i for i, c in enumerate(ITEMS)}

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, i: int):
        r = self.df.iloc[i]
        img = load_rgb(os.path.join(self.data_dir, r["file"]))
        x = self.transform(img)
        cat = self.cat_idx.get(r["category"], IGNORE_INDEX) if isinstance(r["category"], str) else IGNORE_INDEX
        item = self.item_idx[r["item"]] if isinstance(r["item"], str) else IGNORE_INDEX
        return x, cat, item

    def category_counts(self) -> np.ndarray:
        return self.df["category"].value_counts().reindex(CATEGORIES).fillna(0).to_numpy()


def load_manifest(data_dir: str) -> pd.DataFrame:
    path = os.path.join(data_dir, "manifest.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found - run `python -m ml.src.prepare_data` first")
    return pd.read_csv(path)


def class_weights(counts: np.ndarray) -> torch.Tensor:
    """Inverse-frequency weights normalised to mean 1 (sklearn 'balanced' scheme)."""
    counts = np.maximum(counts, 1)
    w = counts.sum() / (len(counts) * counts)
    return torch.tensor(w / w.mean(), dtype=torch.float32)


def make_loaders(data_dir: str, batch_size: int, num_workers: int = 2, image_size: int = 224):
    manifest = load_manifest(data_dir)
    train = WasteDataset(data_dir, manifest, "train", train_transforms(image_size))
    val = WasteDataset(data_dir, manifest, "validation", eval_transforms(image_size))
    test = WasteDataset(data_dir, manifest, "test", eval_transforms(image_size))
    g = torch.Generator()
    g.manual_seed(0)
    kw = dict(num_workers=num_workers, persistent_workers=num_workers > 0)
    return {
        "train": DataLoader(train, batch_size=batch_size, shuffle=True, drop_last=True, generator=g, **kw),
        "validation": DataLoader(val, batch_size=batch_size * 2, shuffle=False, **kw),
        "test": DataLoader(test, batch_size=batch_size * 2, shuffle=False, **kw),
    }, train
