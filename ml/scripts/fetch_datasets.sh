#!/usr/bin/env bash
# Download the raw datasets used by WasteWise v1 into $WASTEWISE_RAW_DIR (default ml/datasets/raw).
#
#   bash ml/scripts/fetch_datasets.sh            # download + extract (~2.5 GB of downloads)
#   bash ml/scripts/fetch_datasets.sh --check    # only verify that the expected folders exist
#
# LICENCES — read before use (details in docs/ml_documentation.md):
#   trashnet     MIT
#   garbage12    ODbL 1.0 (database) / image contents (c) original owners, research use
#   household30  educational, research and non-commercial use; cite Alistair King + Kaggle URL
#   ewastenet    no explicit licence; academic use with citation
# The raw images are NOT redistributed in this repository.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RAW="${WASTEWISE_RAW_DIR:-$ROOT/ml/datasets/raw}"
mkdir -p "$RAW"

declare -A SRC=(
  [trashnet]="https://codeload.github.com/garythung/trashnet/tar.gz/master"
  [garbage12_mirror]="https://codeload.github.com/aesopdev/garbage_classification_model_smam/tar.gz/HEAD"
  [household30]="https://codeload.github.com/AyushKumarSD/Recyclable-and-Household-Waste-Classification/tar.gz/HEAD"
  [ewastenet]="https://codeload.github.com/NifulIslam/EWasteNet-A-Two-Stream-DeiT-Approach-for-E-Waste-Classification/tar.gz/HEAD"
)
# folders prepare_data.py reads (see SOURCE_FOLDERS in ml/src/taxonomy.py)
EXPECT=(
  trashnet/data/dataset-resized/cardboard
  garbage12_mirror/extra/large_garb_dataset/battery
  household30/images/aerosol_cans/real_world
  ewastenet/dataset/Mobile
)

check() {
  local ok=0
  for d in "${EXPECT[@]}"; do
    if [[ -d "$RAW/$d" ]]; then echo "ok       $d ($(find "$RAW/$d" -type f | wc -l) files)"; else echo "MISSING  $d"; ok=1; fi
  done
  return $ok
}

if [[ "${1:-}" == "--check" ]]; then check; exit $?; fi

for name in "${!SRC[@]}"; do
  if [[ -d "$RAW/$name" ]]; then echo "skip $name (exists)"; continue; fi
  echo "downloading $name ..."
  mkdir -p "$RAW/$name"
  curl -fL --retry 3 "${SRC[$name]}" | tar -xz -C "$RAW/$name" --strip-components=1
done
# TrashNet ships its resized images as a zip inside the repository
if [[ ! -d "$RAW/trashnet/data/dataset-resized" ]]; then
  (cd "$RAW/trashnet/data" && unzip -q dataset-resized.zip)
fi
check
echo "next: python -m ml.src.prepare_data --raw-dir \"$RAW\" --out-dir <processed-dir>"
