# Deployment guide

WasteWise runs as three parts:

| Part | Where | Notes |
|---|---|---|
| Frontend (Next.js 15) | Vercel project `wastewise` (root directory `frontend/`) | Proxies `/api/v1/*` to the API on the server side, so the browser only ever talks to one origin (no CORS, no API URL in client bundles) |
| API (FastAPI + ONNX Runtime) | Vercel project `wastewise-api` (root directory `backend/`, Python serverless function `api/index.py`) | Same code runs under `uvicorn`/Docker (`backend/Dockerfile`), so it can move to Render, Railway, Fly.io or Cloud Run without changes |
| Database, auth, storage | Supabase project `tfcwyccbhspkxfttfefc` (ap-south-1) | Migration `supabase/migrations/20261125000001_initial_schema.sql` (RLS on every table, private buckets) |

## Environment variables

### `wastewise-api`

| Key | Value | Type |
|---|---|---|
| `ENVIRONMENT` | `production` (turns off `/docs`) | plain |
| `SUPABASE_URL` | `https://tfcwyccbhspkxfttfefc.supabase.co` | plain |
| `SUPABASE_ANON_KEY` | publishable key (`sb_publishable_…`) | plain |
| `SUPABASE_SERVICE_ROLE_KEY` | dedicated secret key `wastewise_api` (`sb_secret_…`). Used **only** by `DELETE /api/v1/account` | **sensitive** |
| `CORS_ORIGINS` | the frontend production URL (only needed for direct browser calls; the proxy doesn't need it) | plain |

### `wastewise`

| Key | Value |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://tfcwyccbhspkxfttfefc.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | publishable key |
| `API_URL` | production URL of `wastewise-api`, e.g. `https://wastewise-api.vercel.app` |

## Supabase auth settings

* `site_url` = frontend production URL.
* `uri_allow_list` includes `<frontend>/auth/callback` (email confirmation and password reset both land there).
* Email confirmation is on. The built-in Supabase mailer is rate-limited (a few emails per hour) and is meant for testing only. Before real users sign up, configure custom SMTP (Supabase → Authentication → SMTP). This is tracked as Linear MAD-12.

## Serverless notes (Vercel Python)

* The model (about 14 MB ONNX) loads lazily on the first request to each instance. Cold starts are slower, warm requests are fast.
* Request bodies are limited to 4.5 MB by Vercel, so the API limit is 4 MB. The frontend downscales large phone photos (to 2048 px max) before upload.
* The per-user rate limiter (`app/utils/rate_limit.py`) keeps state in memory. On serverless, each instance counts separately, so the limit is per instance. For strict limits, move it to Redis/Upstash or a Postgres counter.
* The ASGI lifespan may not run on serverless. `app/api/deps.py` therefore creates the model session and the Supabase HTTP client lazily if needed.

## Running locally

```bash
# API
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # fill SUPABASE_* values
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm ci
cp .env.example .env.local      # API_URL=http://localhost:8000
npm run dev                     # http://localhost:3000
```

## Docker (any container host)

```bash
docker build -t wastewise-api backend/
docker run -p 8000:8000 --env-file backend/.env wastewise-api
```

The image is non-root and respects `$PORT` and `$WEB_CONCURRENCY`. Its health check calls `/livez`.

## Re-training and re-deploying a model

```bash
bash ml/scripts/fetch_datasets.sh && bash ml/scripts/fetch_pretrained.sh
python -m ml.src.prepare_data --raw-dir ml/datasets/raw --out-dir ml/datasets/processed
python -m ml.src.train --config ml/configs/mobilenet_v3.json      # and the other configs
python -m ml.src.evaluate --experiment exp02_mobilenet_v3_large    # for every experiment
python -m ml.src.select_model --version 1.0.1                      # writes backend/model_artifacts/*
cd backend && pytest                                               # includes real-model parity tests
```

Then commit `backend/model_artifacts/` and `ml/models/best_model.pth`, and redeploy the API.
