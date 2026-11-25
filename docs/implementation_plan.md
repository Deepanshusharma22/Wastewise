# WasteWise — implementation plan and decision log

## Phases

| # | Phase | Linear milestone | Status |
|---|---|---|---|
| 0 | Architecture, repo skeleton, environment, Supabase project | M1 Architecture & Setup | done (Supabase project and schema live) |
| 1 | Dataset and ML pipeline: prepare data, train 3 models | M2 Dataset & ML Pipeline | in progress |
| 2 | Model evaluation, selection, ONNX export, model card | M3 Model Evaluation | code written; runs after training |
| 3 | FastAPI backend (predict, history, analytics, health, model-info) | M4 FastAPI Backend | not started (some modules drafted) |
| 4 | Supabase integration: auth JWT, RLS-scoped data access, private storage + signed URLs | M5 Supabase Integration | schema done |
| 5 | Next.js frontend (EN/HI) | M6 Frontend | not started |
| 6 | Integration, tests, deployment | M7 System Integration, M8 Testing & Deployment | not started |

Each phase ends with a report covering what was implemented, files changed, tests run, errors and limitations, and the next step.

## Architecture (summary)

```
Browser (Next.js on Vercel)
  ├─ Supabase Auth (email/password, reset) ── publishable key only
  └─ HTTPS + user JWT ─▶ FastAPI (Docker; Render or Railway)
                           ├─ verifies JWT via Supabase JWKS (ES256)
                           ├─ onnxruntime model (model_artifacts/) + NumPy Grad-CAM
                           └─ Supabase REST/Storage **with the user's JWT** → RLS enforced
Supabase Postgres: profiles, predictions, feedback, model_metrics (service-role write only)
Supabase Storage: private `waste-images/<user_id>/<yyyy>/<mm>/<prediction_id>.jpg`, signed URLs only
```

## Decisions

| Date | Decision | Reason |
|---|---|---|
| 2026-11-25 | Training on CPU (2 vCPU, no GPU), so epochs and image counts are bounded | sandbox limits; documented in model card |
| 2026-11-25 | MobileNetV3-Large is the deployment candidate; final choice by validation macro-F1 (ties go to lower latency) | 12.6 ms vs 17.6 ms CPU latency |
| 2026-11-25 | API serves ONNX via onnxruntime, without PyTorch at runtime | smaller image and faster cold start; exact Grad-CAM possible in NumPy |
| 2026-11-25 | API calls Supabase with the end user's JWT; the service-role key is used only for account deletion | defence in depth: RLS blocks cross-user access even if API code has a bug |
| 2026-11-25 | **Backend host decided at deployment phase**; Dockerfile kept platform-neutral (`$PORT`) | user choice |
| 2026-11-25 | **Keep household30 and EWasteNet; document the non-commercial / academic-only terms** in README, model card and ML docs | user choice; without them hazardous has no images at all |
| 2026-11-25 | **Keep the Hazardous class and show a limitation notice in the UI** (detection covers aerosol-type items only; the Waste Guide covers other hazardous items in text) | user choice; only 285 aerosol-can images exist |
| 2026-11-25 | User feedback is stored but never used automatically as training labels | requirement |

## Known external constraints

- **Sandbox network:** the sandbox cannot reach `*.supabase.co`.
  - Live backend↔Supabase calls are tested from deployed environments.
  - Unit tests use mocked HTTP and a static JWKS fixture.
- **Supabase built-in email** is rate-limited (about 2 emails per hour). Configure custom SMTP before real users sign up.
- **Supabase Auth URLs:** `site_url` is still `http://localhost:3000`. Set it, and the redirect allow-list, to the Vercel URL when the frontend is deployed.
