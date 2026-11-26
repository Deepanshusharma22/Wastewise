# WasteWise: Final Project Report

**AI waste classification with Indian disposal guidance**
Samsung Innovation Campus capstone, November 2026

- Live web app: https://wastewise-three-lilac.vercel.app
- Live API: https://wastewise-api-three.vercel.app/api/v1/health
- Source: https://github.com/Madhurchaudhary/Wastewise

Every number in this report comes from `ml/reports/` in the repository. These files are produced by the training and evaluation code in `ml/src/`. No metric was typed in by hand, and no prediction is mocked.

---

## 1. Problem and goal

Household waste in India is still mostly mixed at source, even though the Solid Waste Management Rules 2016 require segregation into wet, dry and domestic-hazardous streams. Many people are unsure which bin an item belongs in. They also often don't know that e-waste and aerosol cans need special handling.

WasteWise lets a user photograph one waste item and get back:

1. A category out of 7: organic, paper & cardboard, plastic, metal, glass, e-waste, hazardous. The confidence score is calibrated.
2. A Grad-CAM heat-map showing which part of the image drove the decision.
3. Disposal guidance for India in English and Hindi: bin colour, steps, safety precautions, common mistakes and the relevant rules.
4. A private history and personal analytics, stored in Supabase.

**Design rule:** if the model is not confident, the app says so and asks for a better photo. It never forces a label.

## 2. Architecture

| Layer | Technology | Notes |
|---|---|---|
| ML | PyTorch 2.x and torchvision; ONNX Runtime for inference | Three architectures compared; the winner is exported to ONNX |
| API | FastAPI (Python 3.12) on Vercel | Lazy-bootstrap wrapper; rate limits of 10/min and 300/day per user; 4 MB upload cap |
| Data | Supabase: Auth, Postgres with RLS, private Storage | Each request uses the user's own JWT, so RLS applies. The service key is used only to delete an account |
| Web | Next.js 15, TypeScript, Tailwind, shadcn/ui on Vercel | `/api/v1/*` is proxied server-side to the API; EN/HI; dark theme; respects reduced-motion |

**Pages:** landing, sign-up/login/forgot-password, dashboard, analyze, result, history, analytics, waste guide, settings.

**API endpoints:**
- `GET /health`, `GET /model-info`
- `POST /predict`
- `GET /history`, `GET /history/{id}`, `DELETE /history/{id}`, `PUT /history/{id}/feedback`
- `GET /analytics`, `GET /analytics/category-distribution`
- `DELETE /account`

## 3. Dataset

- **Sources:** 24,284 raw images from public datasets, mapped onto a 7-category, 27-item Indian taxonomy (`ml/src/taxonomy.py`).
- **Cleaning:** exact and near-duplicates were removed. The split was then grouped so that near-duplicates never land on both sides of the train/test boundary.
- **Final split:**

  | Split | Images |
  |---|---|
  | Train | 4,804 |
  | Validation | 1,037 |
  | Test | 1,044 |
  | Out-of-distribution probes (non-waste images, used to test rejection) | 600 |

- **Hazardous class:** 199 / 43 / 43 images (train / validation / test). It covers aerosol cans only.
- **Licensing:** some sources (household30, EWasteNet) are non-commercial / academic only. WasteWise is therefore an academic project. The terms are documented in the README, the model card and `docs/ml_documentation.md`.

## 4. Experiments

All training ran on CPU only (2 cores, about 3.8 GB RAM) with a budget of about 50 minutes per model.

| Experiment | Params | Epochs | Train min | Val acc | Val macro-F1 |
|---|---|---|---|---|---|
| exp01 Custom CNN (from scratch) | 1.96M | 12 | 46.6 | 0.526 | 0.495 |
| exp02 MobileNetV3-Large (ImageNet) | 3.48M | 15 | 47.6 | 0.915 | 0.905 |
| exp03 EfficientNet-B0 (ImageNet) | 4.68M | 10 (early stop, best epoch 6) | 52.3 | 0.914 | 0.908 |

**Selection rule (fixed before looking at the test set):** pick the highest validation macro-F1; if two models are within 0.5 percentage points, pick the one with lower CPU latency. exp02 and exp03 are within 0.3 pp, so **MobileNetV3-Large** was selected (18.1 ms vs 30.1 ms per image in PyTorch on CPU).

## 5. Results on the held-out test set (1,044 images, evaluated once)

| Model | Test acc | Test macro-F1 | ROC-AUC | Hazardous recall | Threshold | Coverage | Acc on accepted | OOD rejected |
|---|---|---|---|---|---|---|---|---|
| exp01 Custom CNN | 0.553 | 0.518 | 0.856 | 0.395 | 0.87 | 3.9% | 92.7% | 99.2% |
| **exp02 MobileNetV3-Large (deployed)** | **0.923** | **0.919** | **0.994** | **0.977** | 0.59 | 94.6% | 94.6% | 35.7% |
| exp03 EfficientNet-B0 | 0.907 | 0.900 | 0.990 | 0.977 | 0.59 | 93.8% | 93.4% | 33.7% |

The selected model is also the best of the three on the test set.

**Deployed model details:**

- **Calibration:** temperature scaling with T = 0.731 reduced test ECE from 0.070 to 0.025.
- **Per-class results (test):**

  | Class | F1 | Recall |
  |---|---|---|
  | Organic | 0.941 | 0.921 |
  | Paper | 0.944 | 0.952 |
  | Plastic | 0.899 | 0.875 |
  | Metal | 0.880 | 0.885 |
  | Glass | 0.913 | 0.911 |
  | E-waste | 0.973 | 0.982 |
  | Hazardous | 0.884 | 0.977 |

- **Size and speed:** 14.1 MB ONNX file; 5.5 ms median ONNX Runtime latency on CPU.
- **Rejection rule:** a prediction is accepted only if the calibrated confidence is at least 0.59 and the gap between the top two classes is at least 0.15. The threshold is the smallest value in [0.50, 0.90] that reaches 95% selective accuracy on the validation set.

**Real-photo check (deployed ONNX model, run locally):** a real photo containing a PET bottle, crumpled paper and a soda can was classified as *plastic* (item: plastic bottle) with 0.992 confidence, in 5.65 ms.

## 6. Limitations (stated honestly)

1. **Out-of-distribution images.** The confidence and margin gate rejects only 35.7% of non-waste probe images. A photo of something that is not waste can still receive a label. The custom CNN's 99% rejection rate is not better behaviour: that model is unsure about almost everything, so it accepts only 3.9% of real test images.
2. **One label per photo.** In the multi-object photo above, only the bottle was labelled; the paper and the can were not. The UI asks for one item per photo.
3. **Narrow hazardous class.** Hazardous detection covers aerosol cans only. The result page shows a notice about this. Other hazardous items (paint, pesticide, medicines, CFLs) are covered in text in the Waste Guide.
4. **Dataset bias.** Most images are web or studio photos with clean backgrounds. Indian street conditions (wet, dirty, partly hidden items) are under-represented. Clear PET bottles versus glass is the most common confusion.
5. **Operations.** The built-in Supabase mailer is rate-limited, so custom SMTP is needed before a public launch. The free Vercel tier has cold starts: the first request after idle loads the model, which took about 3.6 s in our test.

## 7. Future work

- Collect and label photos taken in Indian homes. Fine-tune with the user-feedback table, after manual review.
- Add a dedicated OOD detector (for example energy-based or Mahalanobis) or a "not waste" class.
- Add multi-object detection (YOLO-style) for mixed bins.
- Broaden the hazardous class: batteries, paint, medicines, CFL/tube lights.
- Make the app an installable PWA with on-device ONNX inference (the model is 14 MB).

## 8. Testing and deployment

- **Backend:** 50 automated tests (pytest), all passing. They cover units, the API contract and the real ONNX model.
- **Production smoke checks (25–26 Nov 2026):**
  - `/__bootstrap` reported `ready`.
  - `/api/v1/health` reported `status: ok` with the model loaded.
  - `/api/v1/model-info` returned the model card.
  - Requests through the web proxy reached the API.
  - The login and Waste Guide pages rendered.
- **Results recorded in:**
  - Supabase table `model_metrics` (3 rows)
  - Google Sheets experiment tracker
  - Drive `WasteWise/Model_Evaluation` (confusion matrix, classification report, curves, Grad-CAM sample)
  - Drive `Model_Experiments` (checkpoints)
  - Notion knowledge base
  - Linear project WasteWise (M1–M8)

## 9. Reproducing

See the `README.md` quick start and `docs/deployment.md`. Rebuild the datasets with `ml/scripts/fetch_datasets.sh`. Then run `python -m ml.src.train`, `python -m ml.src.evaluate` and `python -m ml.src.select_model --version 1.0.0`. These regenerate every file in `ml/reports/` and the ONNX model in `backend/model_artifacts/`.
