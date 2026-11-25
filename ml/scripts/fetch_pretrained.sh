#!/usr/bin/env bash
# Download the ImageNet weights used to initialise the transfer-learning models and verify their SHA-256.
#   bash ml/scripts/fetch_pretrained.sh
#
# Primary source: the official torchvision model zoo (BSD-3-Clause). These are the files that
# torchvision's MobileNet_V3_Large_Weights.IMAGENET1K_V1 and EfficientNet_B0_Weights.IMAGENET1K_V1
# resolve to.
# Fallback: byte-identical copies committed to public GitHub repositories, fetched through the
# GitHub git-blob API. This is for networks where download.pytorch.org is blocked. The fallback is
# only accepted if the SHA-256 matches the official checksum, so it cannot substitute other weights.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)/models/pretrained"
mkdir -p "$DIR"

fetch() {  # file sha256 mirror_repo mirror_blob_sha
  local f="$1" sum="$2" repo="$3" blob="$4"
  if [[ ! -f "$DIR/$f" ]]; then
    if ! curl -fsSL --retry 2 -m 300 -o "$DIR/$f.part" "https://download.pytorch.org/models/$f"; then
      echo "download.pytorch.org unreachable, trying GitHub mirror $repo" >&2
      curl -fsSL --retry 2 -m 300 -H "Accept: application/vnd.github.raw" \
        -o "$DIR/$f.part" "https://api.github.com/repos/$repo/git/blobs/$blob"
    fi
    mv "$DIR/$f.part" "$DIR/$f"
  fi
  if ! echo "$sum  $DIR/$f" | sha256sum -c -; then
    echo "checksum mismatch for $f - deleting it" >&2
    rm -f "$DIR/$f"
    exit 1
  fi
}

fetch mobilenet_v3_large-5c1a4163.pth \
  5c1a416349c4cf298f2a6a5e2600ed0ee55e604713578f5e74e6bc8bcaef7997 \
  rlwq/GazyavaTeam 53d9dd65419d3998d4d4684b24e022f19adffb38
fetch efficientnet_b0_rwightman-7f5810bc.pth \
  7f5810bc96def8f7552d5b7e68d53c4786f81167d28291b21c0d90e1fca14934 \
  neuropeopleteam-afk/densitoai 3a060ca4bcbbbdaafc411a2504e3154592a29c2a
