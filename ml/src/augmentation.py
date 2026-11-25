"""Train / eval transforms.

Augmentations are deliberately mild and meaning-preserving: no vertical flips
or large rotations (bottles/cans have a canonical orientation in photos), no
hue shifts large enough to turn green glass into brown glass, no
cut-out/erasing that could hide the only discriminative part of an item.
"""
from __future__ import annotations

from torchvision import transforms as T

from .preprocessing import IMAGE_SIZE, IMAGENET_MEAN, IMAGENET_STD, RESIZE_SIZE


def train_transforms(image_size: int = IMAGE_SIZE) -> T.Compose:
    return T.Compose([
        T.RandomResizedCrop(image_size, scale=(0.6, 1.0), ratio=(0.8, 1.25)),
        T.RandomHorizontalFlip(p=0.5),
        T.RandomRotation(degrees=15, fill=255),
        T.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.15, hue=0.02),
        T.ToTensor(),
        T.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


def eval_transforms(image_size: int = IMAGE_SIZE, resize_size: int = RESIZE_SIZE) -> T.Compose:
    return T.Compose([
        T.Resize(resize_size),
        T.CenterCrop(image_size),
        T.ToTensor(),
        T.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])
