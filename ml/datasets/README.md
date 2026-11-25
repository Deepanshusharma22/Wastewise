# ml/datasets

| Folder | Contents | In git? |
|---|---|---|
| `raw/` | Original downloads (`bash ml/scripts/fetch_datasets.sh`) | no (size and licence terms) |
| `processed/` | Cleaned, de-duplicated images resized to short side 256: `processed/images/<split>/<category>/<uid>.jpg` plus `manifest.csv` | no |
| `train/`, `validation/`, `test/` | Optional split views; `prepare_data` writes splits under `processed/images/<split>/` | no |
| `manifests/manifest_v1.csv` | One row per image: uid, file, split, category, item, source dataset, stratum, source path, md5, dhash, size, near-duplicate group | **yes** (the dataset definition) |

The manifest plus `ml/reports/dataset_report.json` fully define dataset v1. Rebuild it with:

```bash
bash ml/scripts/fetch_datasets.sh
python -m ml.src.prepare_data --raw-dir ml/datasets/raw --out-dir ml/datasets/processed
```

Training and evaluation read `$WASTEWISE_DATA_DIR`, which defaults to `ml/datasets/processed`.
