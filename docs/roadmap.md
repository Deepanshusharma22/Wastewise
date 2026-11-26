# WasteWise — Project Roadmap & Status Audit

_Audited on 2026-11-26 by reading every file in the repository (≈6,600 lines of
Python/TypeScript plus SQL, JSON, notebooks and docs) and then **executing** the
project: backend test suite, the real exported ONNX model, frontend typecheck /
lint / unit tests, and both dev servers._

This document has four parts:

1. [What the system is meant to do](#1-what-the-system-is-meant-to-do)
2. [What we verified by running it](#2-what-we-verified-by-running-it-today)
3. [Status of every phase — done / partial / missing](#3-status-of-every-phase)
4. [The roadmap to "fully working"](#4-the-roadmap-to-fully-working)

---

## 1. What the system is meant to do

WasteWise is an end-to-end AI waste-classification product for India, built for the
Samsung Innovation Campus capstone.

```
Browser (Next.js 15)
  │  auth session cookie (Supabase SSR)
  ├── /api/v1/*  ── server-side proxy ──►  FastAPI (ONNX Runtime)
  │                                          ├─ validate + preprocess image
  │                                          ├─ classify 7 categories (calibrated)
  │                                          ├─ accept / reject ("not sure")
  │                                          ├─ exact Grad-CAM heat-map
  │                                          ├─ fine-grained item label
  │                                          └─ EN/HI disposal guidance
  └── supabase-js ─► Supabase (Auth · Postgres+RLS · private Storage)
```

**Product goal:** photograph one waste item → get a category, a calibrated
confidence, a Grad-CAM explanation, Indian disposal instructions in English and
Hindi, and a private searchable history with personal analytics.

**Design rule the code enforces:** never force a label. If the calibrated
confidence < 0.59 or the top-2 margin < 0.15, the API returns
`is_confident: false` with reasons, and the UI shows an "uncertain" banner.

### The 5 layers and where they live

| Layer | Path | Key files |
|---|---|---|
| ML pipeline | `ml/` | `src/taxonomy.py` (7 categories, 27 items, source folders), `prepare_data.py` (dedupe + group-aware split), `train.py`, `evaluate.py`, `select_model.py` (export ONNX + Grad-CAM head + model card), `metrics.py`, `inference.py` |
| Model artefacts | `backend/model_artifacts/` | `wastewise.onnx` (13.9 MB), `gradcam_head.npz` (1.9 MB), `model_card.json` (metrics, threshold, checksums) |
| API | `backend/app/` | `main.py` (errors, CORS, headers), `api/v1/{predict,history,analytics,system}.py`, `services/{prediction,history,analytics,image,knowledge}_service.py`, `ml/{model_loader,inference,preprocessing}.py`, `utils/{security,validators,rate_limit}.py`, `database/supabase_client.py` |
| Data | `supabase/migrations/` | one migration: 4 tables, RLS everywhere, 2 private storage buckets |
| Web | `frontend/src/` | 12 pages, ~30 components, `lib/api.ts` (typed client), `lib/i18n/` (EN/HI dictionary), `middleware.ts` (session refresh + route guard) |
| Shared | `shared/waste_knowledge.json` → `scripts/sync_shared.py` | one bilingual knowledge base copied into backend + frontend |

---

## 2. What we verified by running it today

Nothing below is taken from the docs — every line is a command that was executed
in this checkout.

| Check | Command | Result |
|---|---|---|
| Backend test suite | `pytest` in `backend/` | **50 collected — 45 passed, 5 skipped, 0 failed.** Skips = torchvision-only pre/post-processing parity tests (`tests/test_units.py:23`). |
| Real exported model loads | `ModelRegistry().load('model_artifacts')` | ✅ `wastewise-classifier 1.0.0-mobilenet_v3_large` |
| Real inference on a real photo | `inference.predict(...)` on `ml/reports/samples/user_photo_input.jpg` | ✅ **plastic, conf 0.9943, confident, item `plastic_bottle`, 5.4 ms** (doc claims 0.992 / 5.65 ms) |
| Exact Grad-CAM | `gradcam()` + `gradcam_overlay_png()` | ✅ 7×7 map, JPEG overlay produced |
| API boots and serves | `uvicorn app.main:app` | ✅ `/api/v1/health` → `model_loaded: true` (degraded only because no Supabase env) |
| Auth is enforced | `POST /api/v1/predict` without token | ✅ **401** |
| Frontend typecheck | `npx tsc --noEmit` | ✅ clean |
| Frontend lint | `npx eslint .` | ✅ clean |
| Frontend unit tests | `npx vitest run` | ✅ 14/14 passed (i18n dictionary, view-model, validation) |
| Next.js builds & serves | `npm run dev` | ✅ `/`, `/guide`, `/login`, `/signup` all 200 |
| Next.js → API proxy | `GET localhost:3000/api/v1/health` | ✅ reaches the FastAPI service |
| Shared knowledge base in sync | `md5sum` of 3 copies | ✅ identical |
| ML results are real | `ml/reports/model_comparison.json`, `exp02/evaluation.json` | ✅ full evaluation artefacts: test acc 0.9234, macro-F1 0.9192, ROC-AUC 0.9935, ECE 0.070→0.0245, threshold 0.59, OOD rejection 0.357 |

**Conclusion: this is not a scaffold.** The ML → ONNX → API → UI vertical slice is
real and works. What is missing is (a) environment wiring that cannot live in git,
(b) production hardening, and (c) some real bugs and inconsistencies listed below.

### Gotcha you will hit locally

`backend/requirements-dev.txt` does not include `onnx`, but
`backend/tests/conftest.py` imports it to build the tiny test graph. Fresh
checkout ⇒ `pytest` dies at collection with `ModuleNotFoundError: No module named 'onnx'`.
Fix: `pip install onnx` (tracked below as roadmap item A3).

---

## 3. Status of every phase

Legend: **✅ done** (works, verified) · **🟡 partial** (works but gaps) ·
**❌ missing** (not built).

### Phase 0 — Architecture, repo skeleton, environment ✅

| Item | Status | Evidence |
|---|---|---|
| Repo layout `ml/ backend/ frontend/ supabase/ shared/ docs/ deploy/ scripts/` | ✅ | present and coherent |
| Settings via env vars (12-factor) | ✅ | `backend/app/config.py` — pydantic-settings, `.env` support |
| Dockerfile (non-root, `$PORT`, healthcheck `/livez`) | ✅ | `backend/Dockerfile` |
| Vercel entry (`backend/index.py`, `backend/vercel.json`) | ✅ | plain ASGI wrapper for Git deploys |
| Supabase project + schema | 🟡 | schema is in the repo; **live project `tfcwyccbhspkxfttfefc` status cannot be verified from here** (no network to `*.supabase.co`) |

### Phase 1 — Dataset & ML pipeline ✅ (finished, better than the plan says)

| Item | Status | Evidence |
|---|---|---|
| Taxonomy: 7 categories, 27 items, 50 source folders incl. OOD probes | ✅ | `ml/src/taxonomy.py` + `validate_taxonomy()` self-check |
| Dataset fetch scripts | ✅ | `ml/scripts/fetch_datasets.sh`, `fetch_pretrained.sh` |
| Prepare data: corruption check, MD5 dedupe, dHash near-dupe union-find, label-conflict removal, capped stratified sampling, **group-aware** 70/15/15 split, OOD probe set | ✅ | `ml/src/prepare_data.py`; `ml/reports/dataset_report.json` |
| Dataset v1 committed as a manifest (7,485 rows) | ✅ | `ml/datasets/manifests/manifest_v1.csv` (train 4,804 / val 1,037 / test 1,044 / ood 600) |
| Train 3 architectures vs budget | ✅ | `exp01_custom_cnn` 0.495, `exp02_mobilenet_v3_large` 0.905, `exp03_efficientnet_b0` 0.908 (val macro-F1) |
| Notebooks 01–04 | ✅ | `ml/notebooks/*.ipynb` with outputs |
| ML unit tests | ✅ | `ml/tests/test_metrics_and_thresholds.py` (synthetic data, no dataset needed) |
| Raw images in git | ✅ correctly excluded | `.gitignore` → `ml/datasets/raw|processed/` |

> ⚠️ `docs/implementation_plan.md` still says Phase 1 "in progress" and Phase 3/5
> "not started". **That document is stale** — this audit replaces it.

### Phase 2 — Evaluation, selection, ONNX export, model card ✅

| Item | Status | Evidence |
|---|---|---|
| Per-model evaluation: accuracy, macro/weighted P/R/F1, ROC-AUC, per-class, confusion matrix, misclassified examples, ECE, selective-prediction curve, OOD rejection, domain accuracy, latency | ✅ | `ml/reports/exp0*/evaluation.json` + PNGs |
| Temperature scaling fitted for calibration | ✅ | T = 0.7307; ECE 0.0700 → 0.0245 |
| Threshold rule (smallest t ∈ [0.5,0.9] reaching 95 % selective accuracy) + margin 0.15 | ✅ | `ml/src/metrics.py`, stored in model card |
| Selection by **validation** macro-F1, tie-break by latency | ✅ | `ml/src/select_model.py`, `ml/reports/model_comparison.md` |
| ONNX export exposing `features` for exact Grad-CAM | ✅ | graph → `image` ⇒ `features`, `category_logits`, `item_logits` |
| Model card with SHA-256 checksums | ✅ | `backend/model_artifacts/model_card.json` |
| Docs auto-filled from artefacts (no hand-typed numbers) | ✅ | `ml/scripts/fill_results.py` |

### Phase 3 — FastAPI backend ✅ (all 10 endpoints implemented)

| Endpoint | Status | Notes |
|---|---|---|
| `GET /api/v1/health`, `GET /livez` | ✅ | reports `model_loaded`, `model_error`, `supabase_configured` |
| `GET /api/v1/model-info` | ✅ | public subset of the model card |
| `POST /api/v1/predict` | ✅ | validate → infer → reliability gate → item head → Grad-CAM → quality hints → upload → insert → signed URL |
| `GET /api/v1/history` | ✅ | filter (category, confident, date range), 4 sort orders, pagination + exact count |
| `GET /api/v1/history/{id}` | ✅ | RLS-scoped, 404 for someone else's row |
| `DELETE /api/v1/history/{id}` | ✅ | row + storage object |
| `PUT /api/v1/history/{id}/feedback` | ✅ | upsert, validation, `verified_label` not user-writable |
| `GET /api/v1/analytics`, `/category-distribution` | ✅ | computed per-user, zero-filled 30-day series, `truncated` flag at 5,000 rows |
| `DELETE /api/v1/account` | ✅ | deletes images, avatar, then auth user via service role; 3/hour |
| Uniform error envelope + `X-Request-ID` + security headers | ✅ | `main.py` exception handlers |
| Rate limiting 10/min, 300/day | ✅ | `utils/rate_limit.py` (in-memory — see P2) |
| JWT verification (ES256 via JWKS / static JWKS / legacy HS256) | ✅ | `utils/security.py`, tested with a real key pair |
| Tests: contract, units, real-model parity, in-memory Supabase fake with RLS emulation | ✅ | 45 passing |

### Phase 4 — Supabase integration 🟡

| Item | Status | Notes |
|---|---|---|
| Schema, indexes, FK cascades | ✅ | `predictions`, `profiles`, `feedback`, `model_metrics` |
| RLS policies on every table + column-level grants | ✅ | e.g. users can update `full_name/avatar_url/prefs/save_images` only |
| `predictions` immutable (no UPDATE policy), `feedback.verified_label` reviewer-only | ✅ | good design |
| Private buckets + path-scoped storage policies | ✅ | `waste-images`, `avatars` |
| Auto-create profile on signup | ✅ | `handle_new_user()` trigger |
| API queries **with the user's JWT** (RLS is the real guard) | ✅ | `database/supabase_client.py` |
| Live project configured (URL, keys, `site_url`, redirect allow-list, SMTP) | ❓ **unverifiable + manual** | must be redone for any new project |
| `model_metrics` rows | 🟡 | table + read policy exist, but **no code writes to it** — the 3 rows were inserted by hand |
| Storage lifecycle (orphan cleanup) | 🟡 | per-request compensation exists; no scheduled sweeper |

### Phase 5 — Next.js frontend ✅ (feature-complete)

| Page / feature | Status |
|---|---|
| Landing, guide (searchable, anchored by category), 404, error boundary | ✅ |
| Signup / login / forgot-password / reset-password / auth callback (PKCE) | ✅ |
| Middleware session refresh + route guard with `?next=` | ✅ |
| Dashboard (KPIs, recent scans, tip of the day) | ✅ |
| Analyze (drag-drop, camera capture, client downscale to 2048 px, scan animation) | ✅ |
| Result (Grad-CAM toggle, confidence ring, top-3, guidance panel, notices, quality warnings, feedback form, delete) | ✅ |
| History (filters, sorting, pagination, delete) | ✅ |
| Analytics (Recharts pie + 30-day bar, 4 KPIs) | ✅ |
| Settings (name, avatar upload, language, theme, save-images privacy toggle, model card, account deletion with typed confirmation) | ✅ |
| EN/हिन्दी switch persisted in cookie + profile, dark theme, `prefers-reduced-motion`, skip link, aria labels | ✅ |
| Typed API client + consistent error keys | ✅ |
| Unit tests | 🟡 14 tests only (no component/flow tests, no E2E) |

### Phase 6 — Integration, testing, deployment 🟡

| Item | Status | Notes |
|---|---|---|
| Backend tests (45 pass) | ✅ | good coverage of API contract + real model |
| Frontend unit tests (14 pass) | 🟡 | no page/component tests |
| E2E tests (Playwright/Cypress) | ❌ | none |
| CI (lint + typecheck + tests on PR) | ❌ | no `.github/workflows/` |
| Docker build of the API | 🟡 | Dockerfile is sound but **not verified here** (no Docker in this sandbox) |
| Vercel deployment procedure | 🟡 | `deploy/vercel/*` pins a **commit that does not exist in this git history** (`2e256724…`) → the API bundle URL would 404; must be regenerated with `scripts/make_vercel_deploy.py` after re-connecting Vercel to GitHub |
| Live URLs in docs | ❓ | `wastewise-three-lilac.vercel.app` / `wastewise-api-three.vercel.app` are from the previous session; not verifiable from here |
| LICENSE file | ❌ | README states licence terms in prose only |

---

## 4. The roadmap to "fully working"

Ordered by what actually blocks a working demo, then a public launch.

### P0 — Make it run end-to-end locally (½ day)

These are the only things standing between this repo and a working local demo.

1. **Create `.env` files** (they are git-ignored on purpose, so a fresh clone has none):
   - `backend/.env` ← `backend/.env.example` + real `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
   - `frontend/.env.local` ← `frontend/.env.example` + `API_URL=http://localhost:8000`
   - _Acceptance:_ `GET /api/v1/health` returns `status: ok` (not `degraded`).
2. **Apply the migration** to a Supabase project (SQL editor or `supabase db push`), then set
   Auth → `site_url = http://localhost:3000` and allow-list `http://localhost:3000/auth/callback**`.
   - _Acceptance:_ sign up → profile row auto-created → `/dashboard` renders.
3. **Fix the dev dependency gap**: add `onnx>=1.16` to `backend/requirements-dev.txt`
   (needed by `conftest.py`), or guard the import in the test fixture.
   - _Acceptance:_ `pytest` runs on a clean venv without a manual install.
4. **Smoke-test the golden path** in a browser: signup → analyze `ml/reports/samples/user_photo_input.jpg`
   → expect *plastic / plastic bottle ~0.99* + Grad-CAM + `/history` + `/analytics` + saved image in
   the private bucket → delete the record → delete the account.

### P1 — Correctness bugs found in the audit (1 day)

Each is small, each has a real user-visible effect.

| # | Bug | Location | Fix |
|---|---|---|---|
| B1 | **Avatar paths are rejected by the API's path validator.** Frontend uploads to `${uid}/avatar.jpg` / `.png` / `.webp`, but `is_owned_storage_path()` only accepts `${uid}/avatar-[0-9a-f]{8}.jpg`. So `DELETE /account` leaves the avatar file orphaned in storage. | `backend/app/utils/validators.py:86` vs `frontend/src/app/settings/page.tsx:80` | Pick one scheme (recommend `avatar.<ext>`), update the regex **and** add a unit test. |
| B2 | **Text-mode prediction rows report no uncertainty reasons.** A result re-opened from `/history/{id}` loses `uncertainty_reasons` (`fromDetail` sets `reasons: []`), while `is_confident: false` still shows the banner — so the chips are missing. | `frontend/src/components/result/view-model.ts`, `backend/app/services/history_service.py` | Either derive reasons from `confidence`/margin in the API detail response, or have the UI compute `low_confidence` from the stored threshold. |
| B3 | **Old rows can 500 the detail endpoint** if `predicted_category` is ever outside the 7 literal values → `knowledge.guidance_for()` raises `KeyError` (schema `Category` Literal). | `history_service.get_detail` → `knowledge.guidance_for` | Guard with a fallback or a 422. |
| B4 | **Stale/contradictory docs**: `docs/implementation_plan.md` says Phase 1 in progress, Phase 3/5/6 not started; `docs/project_tracking.md` and `docs/deployment.md` reference an old Supabase project and Vercel URLs. | `docs/*` | Replace with this roadmap + regenerate deployment notes after the new deployment. |
| B5 | **Deploy bundle pins a non-existent commit** (`2e256724…`). | `deploy/vercel/api/index.py`, `deploy/vercel/web/fetch_source.sh` | Regenerate with `python scripts/make_vercel_deploy.py` once the target commit is pushed (or drop the pinned-upload route and use Vercel ↔ GitHub). |
| B6 | **`model_metrics` has no writer.** The table is read-only for users by design, but no script inserts evaluation results and the frontend never displays them. | `supabase/migrations/...sql:109` | Add `ml/scripts/publish_metrics.py` (service-role) that upserts `ml/reports/*/evaluation.json`. |

### P2 — Production hardening, required before real users (3–5 days)

1. **Move rate limiting off process memory** (`utils/rate_limit.py`) → Redis/Upstash
   or a Postgres counter. Today limits are per serverless instance.
2. **Custom SMTP** in Supabase Auth (the built-in mailer allows only a few mails/hour —
   real signups and password resets will fail silently).
3. **Storage hygiene job**: nightly sweep of `waste-images/<uid>/…` objects with no
   matching `predictions.image_path`, plus abandoned avatar uploads.
4. **Structured error monitoring** (Sentry + request-id correlation) — today only logs.
5. **Cold-start UX**: keep `GET /__bootstrap` diagnostics; add a warm-up ping; consider
   moving `model_artifacts` to object storage with checksum verification (loader already
   supports `MODEL_BASE_URL`).
6. **Privacy/legal**: LICENSE file, privacy policy page, data-retention statement,
   and make the "images are never used for training" claim explicit in the UI.
7. **Accessibility pass**: automated axe check on all 12 pages; keyboard-only run of the
   analyze → result → feedback flow.

### P3 — Quality bar / capstone polish (1 week)

1. **CI**: GitHub Actions — backend `pytest`, `ml/tests`, frontend `tsc`, `eslint`,
   `vitest`, `sync_shared.py --check`. Add `onnx` to dev requirements so CI matches local.
2. **E2E**: Playwright happy path with a seeded test user (signup → predict → history →
   analytics → delete) against a staging Supabase project.
3. **ML tests unskipped**: install torch/torchvision in CI to run the 5 currently
   skipped pre/post-processing parity tests (Pillow-vs-torchvision must stay bit-close,
   otherwise the deployed model sees different pixels than training).
4. **Model improvement roadmap** (already documented in `docs/final_report.md` §7):
   - dedicated OOD detector or "not waste" class — the gate rejects only **35.7 %** of
     non-waste probes, which is the biggest reliability gap;
   - broaden `hazardous` beyond aerosol cans (currently 43 test images, recall 0.977);
   - more Indian real-world photos; clear-PET-vs-glass is the top confusion;
   - multi-object detection (YOLO-style) for mixed bins;
   - PWA with on-device ONNX inference (14 MB model).
5. **Feedback loop**: a reviewer tool that reads `feedback` where
   `verified_label = false`, lets a human verify, and exports a labelled set for the next
   training run. The DB design already supports this; the tool does not exist.

### Suggested sequence (calendar)

| Week | Deliverable |
|---|---|
| W1 | **P0** — local end-to-end demo works; B1–B4 fixed. Capstone demo is safe. |
| W2 | **P2 items 1–3** + **B5/B6**; regenerate deploy, redeploy web + API, re-point Supabase auth URLs. Public-launch ready. |
| W3 | **P3 items 1–3** — CI, E2E, unskipped ML tests; axe pass. Quality bar met. |
| W4+ | **P3 item 4–5** — model/OOD improvements + reviewer feedback tool (research track). |

### Definition of "fully working" (acceptance checklist)

- [ ] Fresh clone + documented env setup ⇒ `pytest` green, `npm run typecheck && lint && test` green.
- [ ] Signup → email confirm → login → analyze → result (category + confidence + Grad-CAM + EN/HI guidance) → history → analytics → delete record → delete account, all in a browser.
- [ ] Uncertain photos return `is_confident: false` with reasons and are never force-labelled.
- [ ] RLS proven by a two-user test: user A can never read/delete user B's prediction or image.
- [ ] CI runs on every PR and is green.
- [ ] Deployed: web + API on Vercel, Supabase Auth URLs + SMTP configured, `/api/v1/health` = `ok`.
- [ ] Docs (this roadmap, API ref, deployment, final report) match the live system.

---

## Appendix — how the pieces connect (quick map)

```
prepare_data.py ─► datasets/processed + manifest_v1.csv
      │
      ├─► train.py (3 configs) ─► models/experiments/<exp>/{best.pth, training_history.json}
      │                                   │
      │                                   ▼
      │                        evaluate.py ─► reports/<exp>/evaluation.json (+ PNGs)
      │                                   │
      │                                   ▼
      └──────────────────────► select_model.py ─► models/best_model.pth
                                                 └─► backend/model_artifacts/
                                                       wastewise.onnx · gradcam_head.npz · model_card.json
                                                             │
                                       model_loader.py (checksum-verified, lazy, thread-safe)
                                                             ▼
   frontend /analyze ──proxy──► predict.py ─► prediction_service ─► inference.py (ONNX + softmax/T + gate)
                                                             │            └► gradcam() (NumPy, analytic)
                                                             ├─► image_service (quality hints, JPEG re-encode)
                                                             ├─► knowledge.py (bilingual guidance + notices)
                                                             └─► SupabaseGateway (user JWT ⇒ RLS) ─► Storage + predictions
                                                                                                        │
   frontend /history, /analytics, /result ◄── history_service / analytics_service ◄────────────────────┘
```
