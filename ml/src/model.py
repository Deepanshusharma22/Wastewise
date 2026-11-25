"""Model architectures: custom CNN baseline, MobileNetV3-Large and EfficientNet-B0.

Every model is a backbone + two heads:
  * ``category_head`` -> 7 waste categories (primary task)
  * ``item_head``     -> fine-grained item types (auxiliary task, partially labelled)

The backend re-implements ``build_model`` in ``backend/app/ml/architectures.py``
(it must not depend on training code); ``backend/tests`` load the real
checkpoint to guarantee both stay in sync.
"""
from __future__ import annotations

import os

import torch
from torch import nn
from torchvision import models

ARCHITECTURES = ("custom_cnn", "mobilenet_v3_large", "efficientnet_b0")

PRETRAINED_FILES = {
    # torchvision IMAGENET1K_V1 weights for both backbones (verified by SHA-256 in fetch_pretrained.sh)
    "mobilenet_v3_large": "mobilenet_v3_large-5c1a4163.pth",
    "efficientnet_b0": "efficientnet_b0_rwightman-7f5810bc.pth",
}


def _conv_block(cin: int, cout: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(cin, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
        nn.Conv2d(cout, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
        nn.MaxPool2d(2),
    )


class CustomCNN(nn.Module):
    """Baseline CNN trained from scratch: 5 conv blocks (conv-BN-ReLU x2 + max-pool)."""

    def __init__(self, widths=(32, 64, 128, 192, 256)):
        super().__init__()
        layers, cin = [], 3
        for w in widths:
            layers.append(_conv_block(cin, w))
            cin = w
        self.features = nn.Sequential(*layers)
        self.out_dim = cin

    def forward(self, x):
        return self.features(x)


class WasteClassifier(nn.Module):
    def __init__(self, arch: str, num_categories: int, num_items: int, dropout: float = 0.3,
                 pretrained_dir: str | None = None):
        super().__init__()
        if arch not in ARCHITECTURES:
            raise ValueError(f"unknown arch {arch}")
        self.arch = arch
        if arch == "custom_cnn":
            self.backbone = CustomCNN()
            feat_dim = self.backbone.out_dim
        elif arch == "mobilenet_v3_large":
            net = models.mobilenet_v3_large(weights=None)
            self._load_pretrained(net, arch, pretrained_dir)
            self.backbone = net.features
            feat_dim = 960
        else:
            net = models.efficientnet_b0(weights=None)
            self._load_pretrained(net, arch, pretrained_dir)
            self.backbone = net.features
            feat_dim = 1280
        self.pool = nn.AdaptiveAvgPool2d(1)
        hidden = 512 if arch != "custom_cnn" else 256
        self.neck = nn.Sequential(nn.Flatten(), nn.Linear(feat_dim, hidden), nn.Hardswish(), nn.Dropout(dropout))
        self.category_head = nn.Linear(hidden, num_categories)
        self.item_head = nn.Linear(hidden, num_items)

    @staticmethod
    def _load_pretrained(net: nn.Module, arch: str, pretrained_dir: str | None) -> None:
        if pretrained_dir is None:
            return
        path = os.path.join(pretrained_dir, PRETRAINED_FILES[arch])
        if not os.path.exists(path):
            raise FileNotFoundError(f"{path} missing - run ml/scripts/fetch_pretrained.sh")
        state = torch.load(path, map_location="cpu", weights_only=True)
        net.load_state_dict(state, strict=True)  # raises if the file doesn't match the architecture

    @property
    def gradcam_layer(self) -> nn.Module:
        """Last convolutional stage — target for Grad-CAM."""
        return self.backbone[-1]

    def freeze_backbone(self, trainable_from: int | None = None) -> None:
        """Freeze backbone stages; stages with index >= trainable_from stay trainable."""
        for i, stage in enumerate(self.backbone):
            trainable = trainable_from is not None and i >= trainable_from
            for p in stage.parameters():
                p.requires_grad = trainable

    def unfreeze_all(self) -> None:
        for p in self.parameters():
            p.requires_grad = True

    def forward(self, x):
        f = self.pool(self.backbone(x))
        h = self.neck(f)
        return self.category_head(h), self.item_head(h)


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())
