# Run WasteWise locally — no Supabase account required (LOCAL MODE)

`LOCAL_MODE=1` swaps the production data layer for a self-contained one so the whole
product can be run and demoed from a clean checkout:

| Production | Local mode |
|---|---|
| Supabase Auth (email links, SMTP) | JWT auth in the API; confirmation links are handed to the UI instead of emailed |
| Supabase Postgres + RLS | SQLite (`backend/.local/wastewise.db`), every query still scoped to `user_id` |
| Supabase private Storage + signed URLs | filesystem (`backend/.local/storage/`) served by `/files/...` with an ownership check |
| ONNX model | **unchanged** — the real 13.9 MB model, real Grad-CAM, real guidance |

Everything else (predict, history, analytics, feedback, settings, EN/HI, Grad-CAM) is
the same code path used in production.

## 1. API

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt

cat > .env <<'EOF'
ENVIRONMENT=development
LOCAL_MODE=1
MODEL_DIR=model_artifacts
PUBLIC_BASE_URL=http://localhost:8000
LOCAL_AUTO_CONFIRM=1
CORS_ORIGINS=http://localhost:3000
EOF

uvicorn app.main:app --host 0.0.0.0 --port 8000   # docs: http://localhost:8000/docs
```

Health should say `"status": "ok"` and `"local_mode": true`:

```bash
curl -s localhost:8000/api/v1/health
```

## 2. Demo account

```bash
python ../scripts/seed_demo.py
# demo account created:  demo@wastewise.local / waste1234
```

The demo account is created **already confirmed** so you can log in immediately.
New sign-ups (any other address) do **not** get auto-confirmed — they get a real
confirmation link, so you can test the flow that used to fail:

1. Open `/signup`, create an account.
2. The "Check your email" screen shows an **Open confirmation link** button (local
   mode has no mailer, so the link is shown rather than sent).
3. The link goes to `/auth/callback?token_hash=…&type=email`, which signs you in and
   redirects to `/dashboard`.
4. Clicking it a second time gives *"This link was already used"* + a
   **Send a new link** action — never a dead end.

`LOCAL_AUTO_CONFIRM=0` in `backend/.env` makes *every* sign-up go through the link
(useful when you want to demo the confirmation flow with the demo address too).

## 3. Web

```bash
cd frontend
npm ci
echo "API_URL=http://localhost:8000" > .env.local     # no Supabase keys needed
npm run dev                                           # http://localhost:3000
```

The web app asks the API once (`GET /api/v1/local-info`) which mode it is in:

- **local** → auth/profile/avatar go through the API (token kept in `localStorage`),
  and the Supabase route guard in `middleware.ts` steps aside.
- **not local** → the original Supabase path is used, unchanged.

## 4. What to click

| Page | What to check |
|---|---|
| `/signup` → link → `/dashboard` | the confirmation link works (this was the bug) |
| `/analyze` | upload `ml/reports/samples/user_photo_input.jpg` → *plastic · plastic bottle · ~99%* + Grad-CAM |
| `/result/<id>` | guidance in EN and हिन्दी, heat-map toggle, feedback form |
| `/history` | filters, sorting, pagination, delete |
| `/analytics` | pie + 30-day bars |
| `/settings` | name, avatar (stored as `<uid>/avatar-<8hex>.jpg`), language, theme, "save images" toggle, delete account |
| `/login` | wrong password → clean error; unconfirmed account → "confirm your email" + resend |

## 5. Tests

```bash
cd backend
pytest                            # Supabase-mode contract suite (unchanged)
pytest -c pytest-local.ini        # 18 local-mode end-to-end tests, incl. the link flows
```

## 6. Back to production

Remove/disable `LOCAL_MODE`, fill `backend/.env` with the Supabase values from
`backend/.env.example`, and set `frontend/.env.local` to the Supabase keys. Nothing in
the code needs to change; local mode is inert unless the API reports it.

> Local mode is for development and demos only: passwords are PBKDF2-hashed in SQLite,
> tokens are HS256 with a default secret, and files sit unencrypted on disk.
> Never deploy with `LOCAL_MODE=1`.
