# Fixes applied — 2026-11-26

Every item from `docs/bugs-and-gaps.md` plus the login bug is fixed, and the app now
runs (and can be logged into) without a Supabase project.

Verification status of this change set:

| Check | Command | Result |
|---|---|---|
| Supabase-mode contract suite | `cd backend && pytest` | **45 passed, 5 skipped** |
| Local-mode end-to-end suite | `cd backend && pytest -c pytest-local.ini` | **18 passed** |
| Web typecheck / lint / unit tests | `npm run typecheck && npm run lint && npm test` | clean, **14 passed** |
| Web production build | `npm run build` | ✅ 15 routes |
| Real model through the web proxy | `POST /api/v1/predict` | plastic · 0.9943 · plastic_bottle · Grad-CAM |
| Private image access | `GET /files/...` with/without token | **200 / 401** |

---

## 1. The login / email-confirmation bug (your report)

**Root cause:** `src/app/auth/callback/route.ts` only understood `?code=` (Supabase PKCE).
Supabase's default template sends `?token_hash=…&type=…`, and any other shape fell to a
hard-coded *"The link is invalid or has expired"* — no resend, no code entry, no way out.

| Fix | Where |
|---|---|
| Callback accepts `?code=`, `?token_hash=&type=`, and reports the **specific** failure (`link_expired`, `link_used`, `invalid_link`, `unsupported_link`, `api_unreachable`) | `frontend/src/app/auth/callback/route.ts` |
| Works on **any device/browser** (token_hash + `verifyOtp`, no PKCE cookie needed) | same |
| Failure lands on `/login?error=…&reason=…&email=…`, which renders **"Send me a new link"** instead of a dead end | `frontend/src/app/(auth)/login/page.tsx` |
| **Resend confirmation** everywhere (signup "check email" screen + login error panel) | `login`, `signup` |
| **6-digit code** entry (`verifyOtp`) for projects whose template sends a number | `login` |
| Redirect origin honours `x-forwarded-host`, so preview/proxy hosts don't break links | `auth/callback/route.ts` |
| Link tokens are **single use**; reused/expired links say so explicitly | `backend/app/api/v1/local_auth.py`, `local_store.used_link_tokens` |
| Password recovery gets its own link + `/reset-password` path, and never silently fails | `forgot-password`, `reset-password` |
| Real bugs in signup: `sent` was shown even when the mail was rate-limited; `setBusy(false)` skipped on error | `signup/page.tsx` |

**Production checklist that goes with it** (Supabase dashboard — cannot be done from code):
`Site URL` = your deployed web URL · `Redirect URLs` = `<web>/auth/callback`,
`http://localhost:3000/auth/callback`, plus any preview host · configure custom SMTP
(the built-in mailer allows ~2 mails/hour) · optionally point the email templates at
`{{ .SiteURL }}/auth/callback?token_hash={{ .TokenHash }}&type=email&next=/dashboard`.

## 2. Local mode — the project now runs and is loggable-in without Supabase

| Piece | File |
|---|---|
| `LOCAL_MODE` setting, DB/storage paths, auth rates, `data_configured` | `backend/app/config.py` |
| SQLite store implementing the **same interface** as `SupabaseGateway` (PostgREST-style filters, `user_id` scoping = RLS) | `backend/app/database/local_store.py` |
| Auth: signup, email link, resend, login, recover, reset, password change, logout | `backend/app/api/v1/local_auth.py` |
| Signed JWT + **single-use** link tokens (PBKDF2 password hashing) | `backend/app/utils/local_auth.py` |
| File serving with ownership check (`<uid>/…` only) | `backend/app/api/v1/files.py` |
| Profile read/update + avatar upload (works in both modes) | `backend/app/api/v1/profile.py`, `services/avatar_service.py` |
| Mode-aware auth dependency (local JWT vs Supabase JWT) | `backend/app/api/deps.py`, `utils/security.py` |
| Frontend `Backend` interface: `LocalBackend` / `SupabaseBackend` | `frontend/src/lib/backend/index.ts` |
| Route guard steps aside in local mode | `frontend/src/middleware.ts` |
| `/files/*` proxied to the API (same-origin, no `localhost:8000` in the page) | `frontend/next.config.ts` |
| Demo seeding | `scripts/seed_demo.py` |
| Guide | `docs/local-demo.md` |

## 3. Every other bug from the audit

| # | Bug | Fix | Test |
|---|---|---|---|
| B1 | **HEIC photos from iPhones were rejected (415)** | `normalizeImageToJpeg()` decodes any browser-readable image (incl. HEIC/HEIF) and re-encodes to JPEG before upload; analyze accepts them and only falls back to an error if decoding truly fails | `test_heic_upload_is_rejected_with_a_clear_code` |
| B2 | **Avatar path mismatch** → account deletion orphaned avatars | Server generates `<uid>/avatar-<8hex>.<ext>`; validator accepts exactly jpg/png/webp of that shape (+ rejects `..`); shared helper in `lib/avatar.ts` | `test_avatar_path_matches_what_account_deletion_accepts`, `test_account_deletion_removes_rows_and_avatar` |
| B3 | **`model_metrics` had no writer** | `ml/scripts/publish_metrics.py` upserts one row per experiment from `ml/reports/*/evaluation.json` (dry-run verified: 0.9234 / 0.9192 / 0.9377) | `--dry-run` |
| B4 | **Deploy bundle pinned a non-existent commit** | Repointed to a real commit, empty checksum now *refuses to start*, `fetch_source.sh` takes the SHA as an argument | — |
| B5 | **Stale docs** | `implementation_plan.md` and `project_tracking.md` marked stale; this file + `roughmap`/`local-demo` supersede them | — |
| B6 | **`pytest` failed on a clean checkout (`onnx` missing)** | Added `onnx` to `requirements-dev.txt`; `pydantic[email]` for email validation | CI |
| B7 | **History-opened results lost uncertainty reasons** | Reasons are persisted (`predictions.uncertainty_reasons`), returned by `/history/{id}`, and rendered by `fromDetail()` | `test_predict_history_and_reasons_round_trip` |
| B8 | **Detail endpoint could 500 on an unknown category** | `knowledge.safe_guidance_for()` + `.get()` in `is_recyclable` | covered by the same test |
| B9 | **No CI** | `.github/workflows/ci.yml`: backend (both suites), web (typecheck, lint, tests, build), shared-knowledge sync check | — |
| B10 | **No E2E of the login flow** | 18-test local-mode suite covers signup → link → session → predict → history → avatar → delete, plus link reuse/expiry/resend | — |
| new | Concurrent scans shared one ONNX session | `inference_lock` serialises infer + Grad-CAM | — |

## 4. Tests added

`backend/tests_local/test_local_mode.py` (run with `pytest -c pytest-local.ini`):

1. health/local-info/mode
2. data endpoints require a token
3. signup returns a session when auto-confirm is on
4. duplicate signup rejected (409)
5. weak password rejected (422)
6. unconfirmed user cannot log in (403 + code)
7. wrong password is a clean 401
8. **confirmation link works once, then reports "already used"**
9. expired/tampered link rejected
10. resend says "already confirmed" when appropriate
11. password reset flow end-to-end
12. predict → history → reasons → analytics → delete, with the real model
13. two users cannot see each other's rows (RLS equivalent)
14. HEIC upload gets a clear 415
15. avatar path shape matches the validator
16. preferences persist and `save_images=false` stops image storage
17. account deletion removes the user, rows and avatar

## 5. How to run it (short version)

```bash
# API (local mode, no Supabase)
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
printf 'LOCAL_MODE=1\nMODEL_DIR=model_artifacts\nLOCAL_AUTO_CONFIRM=1\n' > .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
python ../scripts/seed_demo.py          # demo@wastewise.local / waste1234

# Web
cd frontend && npm ci && echo 'API_URL=http://localhost:8000' > .env.local && npm run dev
```

Full walkthrough, including how to exercise the confirmation-link flow on purpose:
**`docs/local-demo.md`**.
