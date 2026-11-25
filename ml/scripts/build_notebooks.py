"""Generate the four research notebooks from code (keeps them reviewable and in sync with src/).

    python ml/scripts/build_notebooks.py
    WASTEWISE_DATA_DIR=/path/to/processed jupyter nbconvert --execute --inplace ml/notebooks/01_dataset_exploration.ipynb

Notebooks are thin, executed views over the reproducible CLI modules in ml/src —
training itself runs through `python -m ml.src.train` (long-running, checkpointed),
not inside a notebook.
"""
from __future__ import annotations

from pathlib import Path

import nbformat as nbf

OUT = Path(__file__).resolve().parents[1] / "notebooks"

SETUP = """import os, sys, json
from pathlib import Path
ROOT = Path.cwd()
while not (ROOT / 'ml' / 'src').exists() and ROOT != ROOT.parent:
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)
DATA_DIR = os.environ.get('WASTEWISE_DATA_DIR', str(ROOT / 'ml/datasets/processed'))
import numpy as np, pandas as pd, matplotlib.pyplot as plt
pd.set_option('display.width', 160)"""


def nb(cells):
    n = nbf.v4.new_notebook()
    n.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    n.cells = [nbf.v4.new_markdown_cell(c[3:]) if c.startswith("md:") else nbf.v4.new_code_cell(c) for c in cells]
    return n


NB01 = [
    "md:# 01 · Dataset exploration\n\nDataset **v1** built by `python -m ml.src.prepare_data`. Sources, licences, cleaning statistics and class "
    "distribution all come from `ml/reports/dataset_report.json` and the manifest — nothing in this notebook is typed in by hand.",
    SETUP,
    "rep = json.load(open('ml/reports/dataset_report.json'))\n"
    "pd.DataFrame(rep['sources']).T[['name', 'license', 'url']]",
    "md:## Cleaning summary",
    "keys = ['raw_total_in_taxonomy', 'exact_duplicates_removed', 'exact_duplicate_label_conflicts_dropped',\n"
    "        'near_duplicate_groups', 'near_duplicate_cross_dataset_groups', 'near_duplicate_images_collapsed',\n"
    "        'near_duplicate_label_conflicts_dropped', 'imbalance_ratio_max_min']\n"
    "pd.Series({k: rep[k] for k in keys})",
    "md:## Class distribution per split",
    "m = pd.read_csv('ml/datasets/manifests/manifest_v1.csv', dtype={'uid': str})\n"
    "lab = m[m.split != 'ood']\ntab = pd.crosstab(lab['category'], lab['split'])[['train', 'validation', 'test']]\n"
    "display(tab)\n"
    "ax = tab.plot.bar(stacked=True, figsize=(9, 4), color=['#238B67', '#B8E986', '#123D32'])\n"
    "ax.set_ylabel('images'); ax.set_title('Images per category and split (OOD probes excluded)'); plt.tight_layout()",
    "md:## Source dataset per category (domain mix)",
    "display(pd.crosstab(lab['category'], lab['dataset']))\nprint('OOD probe images (never trained on):'); m[m.split == 'ood']['stratum'].value_counts()",
    "md:## Leakage check — no near-duplicate group may span two splits",
    "g = m[m.split != 'ood'].groupby('group')['split'].nunique()\n"
    "print('groups spanning >1 split:', int((g > 1).sum()))\n"
    "print('duplicate md5 across manifest:', int(m['md5'].duplicated().sum()))",
    "md:## Sample images",
    "from PIL import Image\n"
    "cats = list(m['category'].dropna().unique())\n"
    "fig, axes = plt.subplots(len(cats), 6, figsize=(12, 2.1 * len(cats)))\n"
    "for r, c in enumerate(sorted(cats)):\n"
    "    s = m[(m.category == c) & (m.split == 'train')].sample(6, random_state=0)\n"
    "    for k, (_, row) in enumerate(s.iterrows()):\n"
    "        ax = axes[r, k]; ax.imshow(Image.open(os.path.join(DATA_DIR, row['file']))); ax.axis('off')\n"
    "        if k == 0: ax.set_title(c, loc='left', fontsize=9)\n"
    "plt.tight_layout()",
    "md:## Source image sizes (as found in the raw datasets, before resizing to short side 256)",
    "m[['width', 'height']].describe()",
    "md:### Known limitations\n- **Hazardous** = aerosol cans only (285 unique images); no public hazardous-waste dataset was found. "
    "Class weights compensate for imbalance but cannot add missing visual variety.\n"
    "- household30 is licensed for *educational / research / non-commercial* use; EWasteNet has no explicit licence "
    "(academic use with citation). The trained model inherits these restrictions.",
]

NB02 = [
    "md:# 02 · Training\n\nAll models are trained with `python -m ml.src.train --config ml/configs/<name>.json` "
    "(AdamW, class-weighted cross-entropy, cosine schedule, early stopping on validation macro-F1, seed 42). "
    "This notebook loads the recorded histories.",
    SETUP,
    "cfgs = {p.stem: json.load(open(p)) for p in sorted(Path('ml/configs').glob('*.json'))}\n"
    "pd.DataFrame(cfgs).T",
    "hist = {}\n"
    "for d in sorted(Path('ml/models/experiments').glob('*/training_history.json')):\n"
    "    hist[d.parent.name] = pd.DataFrame(json.load(open(d))['history'])\n"
    "list(hist)",
    "fig, axes = plt.subplots(1, 3, figsize=(16, 4))\n"
    "for name, h in hist.items():\n"
    "    axes[0].plot(h['epoch'], h['train_loss'], '--', label=f'{name} train'); axes[0].plot(h['epoch'], h['val_loss'], label=f'{name} val')\n"
    "    axes[1].plot(h['epoch'], h['val_acc'], label=name); axes[2].plot(h['epoch'], h['val_f1_macro'], label=name)\n"
    "for ax, t in zip(axes, ['loss', 'validation accuracy', 'validation macro-F1']): ax.set_title(t); ax.set_xlabel('epoch'); ax.legend(fontsize=7)\n"
    "plt.tight_layout()",
    "summ = {d.parent.name: json.load(open(d)) for d in sorted(Path('ml/models/experiments').glob('*/train_summary.json'))}\n"
    "pd.json_normalize(list(summ.values())).set_index('experiment_id').drop(columns=['checkpoint'])",
]

NB03 = [
    "md:# 03 · Evaluation & model selection\n\nProduced by `python -m ml.src.evaluate --experiment <id>` (temperature and confidence "
    "threshold fitted on **validation**; test evaluated once) and `python -m ml.src.select_model`.",
    SETUP,
    "from IPython.display import Image as Img, Markdown\n"
    "display(Markdown(Path('ml/reports/model_comparison.md').read_text()))",
    "from ml.src.taxonomy import CATEGORIES\n"
    "evals = {p.parent.name: json.load(open(p)) for p in sorted(Path('ml/reports').glob('*/evaluation.json'))}\n"
    "for k, e in evals.items():\n"
    "    print(k); display(pd.DataFrame(e['test']['per_class']).T.loc[list(CATEGORIES)].round(3))",
    "sel = json.load(open('ml/reports/model_comparison.json'))['selected']; print('selected:', sel)\n"
    "Img(f'ml/reports/{sel}/confusion_matrix.png')",
    "Img(f'ml/reports/{sel}/selective_curve.png')",
    "e = evals[sel]\n"
    "pd.Series({'temperature': e['temperature'], 'threshold': e['confidence_threshold'], **e['test_selective'],\n"
    "           'ood_rejection_rate': e['ood']['rejection_rate']})",
    "md:### Safety-relevant classes and most frequent confusions",
    "display(pd.DataFrame(e['safety_classes']).T)\npd.DataFrame(e['top_confusions'])",
    "md:### Misclassified test images (safety-relevant errors first)",
    "Img(f'ml/reports/{sel}/misclassified.jpg')",
]

NB04 = [
    "md:# 04 · Inference & explainability\n\nUses the deployment checkpoint `ml/models/best_model.pth` through `ml.src.inference.WastePredictor` "
    "(Top-3, calibrated threshold, Grad-CAM) on held-out **test** images, and checks parity with the exported ONNX graph used by the API.",
    SETUP,
    "from ml.src.inference import WastePredictor, overlay\nfrom ml.src.preprocessing import load_rgb\n%matplotlib inline  # ml.src.evaluate selects the Agg backend on import\n"
    "pred = WastePredictor('ml/models/best_model.pth')\nprint('threshold', pred.threshold, 'temperature', pred.temperature)",
    "m = pd.read_csv('ml/datasets/manifests/manifest_v1.csv', dtype={'uid': str})\n"
    "sample = pd.concat([m[(m.split == 'test') & (m.category == c)].sample(1, random_state=3) for c in sorted(m['category'].dropna().unique())]\n"
    "                   + [m[m.split == 'ood'].sample(2, random_state=3)])\n"
    "fig, axes = plt.subplots(2, len(sample), figsize=(2.3 * len(sample), 5.2))\n"
    "for k, (_, row) in enumerate(sample.iterrows()):\n"
    "    img = load_rgb(os.path.join(DATA_DIR, row['file'])); p = pred.predict(img)\n"
    "    axes[0, k].imshow(img); axes[0, k].axis('off'); axes[0, k].set_title(f\"true: {row['category'] if row['split'] != 'ood' else 'OOD'}\", fontsize=8)\n"
    "    axes[1, k].imshow(overlay(img, pred.gradcam(img, p.category))); axes[1, k].axis('off')\n"
    "    lab = f'{p.category} {p.confidence:.2f}' if p.is_confident else f'uncertain ({p.category} {p.confidence:.2f})'\n"
    "    axes[1, k].set_title(lab, fontsize=8, color='black' if p.is_confident else 'red')\n"
    "plt.tight_layout()",
    "md:## ONNX parity (the API runs `backend/model_artifacts/wastewise.onnx`)",
    "import onnxruntime as ort, torch\nfrom ml.src.augmentation import eval_transforms\n"
    "sess = ort.InferenceSession('backend/model_artifacts/wastewise.onnx', providers=['CPUExecutionProvider'])\n"
    "diffs = []\n"
    "for _, row in sample.iterrows():\n"
    "    x = eval_transforms()(load_rgb(os.path.join(DATA_DIR, row['file']))).unsqueeze(0)\n"
    "    with torch.no_grad(): ref, _ = pred.model(x)\n"
    "    diffs.append(float(np.abs(sess.run(None, {'image': x.numpy()})[1] - ref.numpy()).max()))\n"
    "print('max |logit difference| torch vs onnx:', max(diffs))",
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, cells in [("01_dataset_exploration", NB01), ("02_training", NB02),
                        ("03_evaluation", NB03), ("04_inference_and_explainability", NB04)]:
        nbf.write(nb(cells), OUT / f"{name}.ipynb")
        print("wrote", name)


if __name__ == "__main__":
    main()
