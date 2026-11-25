# WasteWise — ML documentation

> Every number in this document is produced by code in `ml/src` and stored in `ml/reports/`.
> Sections marked *(generated)* are copied from those report files after evaluation runs.

## 1. Problem definition

Single-image classification of one household waste item into **7 categories**:
`organic, paper_cardboard, plastic, metal, glass, e_waste, hazardous`.
An auxiliary head predicts one of 27 fine-grained item types (for example `aluminium_can` or `battery`). The UI shows it only when it is confident.
The label taxonomy and its mapping from source datasets live in `ml/src/taxonomy.py`, which is the single source of truth.

## 2. Datasets and licences

| Dataset | Use | Licence / terms |
|---|---|---|
| TrashNet (Thung & Yang) | paper, cardboard, glass, metal, plastic | MIT |
| Garbage Classification 12 (Kaggle, mostafaabla) | battery, biological, glass, paper, metal, plastic | ODbL 1.0 (database); images © original owners, research use |
| Recyclable & Household Waste (Kaggle, Alistair King) | 30 item classes, including the only aerosol-can images | Card says educational, research and non-commercial use; requires citation |
| EWasteNet (Nifulislam) | 8 electronic-device classes | No explicit licence; academic use with citation |

**Consequence:** the trained weights inherit **non-commercial / research-only** restrictions. WasteWise is an educational capstone. Commercial use would need re-licensed or self-collected data.
Raw datasets are **not** committed or copied to cloud drives. `python -m ml.src.prepare_data` rebuilds dataset v1 deterministically from the original sources.

Images from TrashNet "trash", Garbage-12 clothes/shoes/trash and household30 paper cups, clothing and shoes are held out as **out-of-distribution (OOD) probes**. They are never trained on. They measure how often the confidence threshold rejects things that are not one of the 7 categories.

## 3. Data cleaning and leakage prevention (`ml/src/prepare_data.py`)

1. **Decode check.** Every file is opened with Pillow, EXIF-transposed and converted to RGB. Unreadable files are listed in the report.
2. **Exact duplicates (MD5).** These are removed. If identical files carry conflicting labels, the file is dropped. Garbage-12's paper/plastic/metal/cardboard/glass folders turned out to be byte-identical copies of TrashNet.
3. **Near duplicates.** A 32×32 grayscale thumbnail correlation (≥ 0.97) plus a 4×4 colour-layout check finds them, and union-find joins them into groups.
   - A 64-bit dHash was tried first and rejected: centred objects on white backgrounds collapsed into huge false groups.
   - Pairs at ≥ 0.99 are collapsed to one image.
   - Groups whose members carry conflicting labels are dropped.
4. **Group-aware stratified split (70/15/15, seed 42).** A near-duplicate group always goes to a single split, so no visually identical image appears in both train and test. Notebook 01 re-checks this: *0 groups span more than one split, 0 duplicate MD5s*.
5. **Class balance.** Each category is capped at 1,100 images. `hazardous` has only 285 unique images; this gap is compensated by inverse-frequency class weights in the loss.

Dataset statistics *(generated)* are in `ml/reports/dataset_report.json` and `ml/notebooks/01_dataset_exploration.ipynb`.

## 4. Preprocessing and augmentation

- **Eval / inference:** resize the short side to 256 (bilinear), centre-crop 224, then ImageNet mean/std normalisation. The API reimplements this in NumPy (`backend/app/ml/preprocessing.py`), and a parity test checks it against torchvision.
- **Training:** RandomResizedCrop(224, scale 0.6–1.0), horizontal flip, ±15° rotation, mild colour jitter (hue ±0.02 so green and brown glass keep their colour).
  - No vertical flips.
  - No random erasing.

## 5. Models compared

| Experiment | Architecture | Init | Notes |
|---|---|---|---|
| exp01_custom_cnn | 5-block CNN (conv-BN-ReLU ×2 + max-pool) | random | baseline |
| exp02_mobilenet_v3_large | MobileNetV3-Large | ImageNet (torchvision V2) | deployment candidate (fast on CPU) |
| exp03_efficientnet_b0 | EfficientNet-B0 | ImageNet (torchvision V1) | accuracy reference |

All three share the head: global pool → Linear (512, or 256 for the CNN) → Hardswish → Dropout → {category head, item head}.

**Training** (`ml/src/train.py`, configs in `ml/configs/`):
- AdamW with weight decay.
- Class-weighted cross-entropy; the item loss has weight 0.3 and ignores unlabelled items.
- Pretrained nets get a frozen-backbone warm-up (lr 1e-3), then partial unfreezing (lr 3e-4) with a cosine schedule.
- Batch size 32.
- Early stopping on **validation macro-F1**, with checkpointing of the best epoch.
- Fixed seeds; CPU-only (2 vCPU).

## 6. Evaluation protocol (`ml/src/evaluate.py`)

1. **Temperature scaling** is fitted on validation logits (NLL).
2. **Confidence threshold:** the smallest threshold in [0.50, 0.90] whose validation selective accuracy is ≥ 95%. If none qualifies, the fallback is 0.65.
   - A prediction is "confident" only if p₁ ≥ threshold **and** p₁ − p₂ ≥ 0.15.
   - Otherwise the user sees: *"Unable to confidently identify this waste item. Please upload a clearer image."*
3. **Test split, evaluated once per model, after selection settings are frozen.** It reports:
   - accuracy, macro/weighted precision, recall and F1, per-class report, confusion matrix and one-vs-rest ROC-AUC;
   - ECE;
   - coverage and accuracy at the threshold;
   - per-source-dataset accuracy;
   - OOD rejection rate;
   - hazardous and e-waste safety statistics;
   - CPU latency.
4. **Model selection** (`ml/src/select_model.py`): highest *validation* macro-F1; ties within 0.5 pp go to the lower CPU latency. Test numbers are reported but never used for the choice.

## 7. Results *(generated)*

The model comparison is in `ml/reports/model_comparison.md`. Per-model details are in `ml/reports/<experiment>/evaluation.json`, `confusion_matrix.png`, `selective_curve.png` and `misclassified.jpg`. The experiment log is `ml/reports/experiment_log.csv`.

<!-- RESULTS:START -->
_Pending: filled in from `ml/reports/model_comparison.md` after all experiments are evaluated._
<!-- RESULTS:END -->

## 8. Deployment artefacts

`select_model.py` exports the chosen model to `backend/model_artifacts/`:
- `wastewise.onnx`: input `image` (N×3×224×224); outputs `features` (last conv map), `category_logits` and `item_logits`.
- `gradcam_head.npz`: head weights. Because the head is pool → Linear → Hardswish → Linear, the gradient of a class logit with respect to the feature map has a closed form. The API therefore computes **exact Grad-CAM in NumPy** without PyTorch.
- `model_card.json`: version, SHA-256, temperature, threshold, metrics, licences and limitations.

The API image needs only `onnxruntime` + NumPy + Pillow, not PyTorch.

## 9. Known limitations

- **Hazardous = aerosol cans only.** Paint, chemicals, medicines, thermometers and similar items are not in any public dataset that was found, so the model cannot recognise them. The waste guide covers them in text.
- **E-waste** covers batteries plus 8 device types; cables, chargers and PCBs are missing.
- The training images are mostly single, centred objects on clean backgrounds. Expect lower reliability on cluttered or mixed-waste photos.
- Confidence is a calibrated estimate, not a guarantee.
- User feedback is stored for review but **never** fed back automatically as training labels.

## 10. Reproduce

```bash
python -m ml.src.prepare_data --raw-dir <raw> --out-dir <processed>
export WASTEWISE_DATA_DIR=<processed>
for c in custom_cnn mobilenet_v3 efficientnet_b0; do python -m ml.src.train --config ml/configs/$c.json; done
for e in exp01_custom_cnn exp02_mobilenet_v3_large exp03_efficientnet_b0; do python -m ml.src.evaluate --experiment $e; done
python -m ml.src.select_model --version 1.0.0
python -m pytest ml/tests -q
```
