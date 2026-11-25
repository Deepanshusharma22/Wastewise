#!/usr/bin/env bash
# Download the ImageNet weights used to initialise the transfer-learning models and verify their SHA-256.
#   bash ml/scripts/fetch_pretrained.sh
# Source: official torchvision model zoo (BSD-3-Clause), the same files torchvision's
# MobileNet_V3_Large_Weights.IMAGENET1K_V2 and EfficientNet_B0_Weights.IMAGENET1K_V1 resolve to.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)/models/pretrained"
mkdir -p "$DIR"
fetch() {  # file sha256
  local f="$1" sum="$2"
  if [[ ! -f "$DIR/$f" ]]; then curl -fL --retry 3 -o "$DIR/$f" "https://download.pytorch.org/models/$f"; fi
  echo "$sum  $DIR/$f" | sha256sum -c -
}
fetch mobilenet_v3_large-5c1a4163.pth 5c1a416349c4cf298f2a6a5e2600ed0ee55e604713578f5e74e6bc8bcaef7997
fetch efficientnet_b0_rwightman-7f5810bc.pth 7f5810bc96def8f7552d5b7e68d53c4786f81167d28291b21c0d90e1fca14934
