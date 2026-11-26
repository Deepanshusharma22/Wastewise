# WasteWise — Major bugs & where the project lags

> **Status update (same day):** every item below is fixed in code and covered by tests.
> See `docs/fixes-applied.md` for the change list, and `docs/local-demo.md` to run the app
> and log in without Supabase. The analysis here is kept for reference.

_Report date 2026-11-26. Everything here was checked against the code and, where
possible, reproduced with a running server (not guessed)._

Your symptom: **"signup → email → click the link → 'the link is invalid or has
expired', and it stays broken until I open it in a new tab / re-request it, so I
can never log in."**

That is not one bug. It is **one broken flow with 6 separate causes**, plus a
configuration trap. Details in §1. The rest of the report lists the other major
bugs (§2), performance/lag (§3) and the fix order (§4).

---

## 1. The login / email-confirmation bug (your exact problem)

### How the flow is wired today

```
signup page ──signUp({emailRedirectTo: "<origin>/auth/callback?next=/dashboard"})──► Supabase
                                                                                       │ sends email
email link ──► https://<project>.supabase.co/auth/v1/verify?token=<OTP>&type=signup&redirect_to=<origin>/auth/callback?next=/dashboard
                        │  Supabase verifies, CONSUMES the OTP, then 302s to redirect_to with ?code=...
                        ▼
     /auth/callback?code=...  →  exchangeCodeForSession(code)  →  sets cookies  →  /dashboard
```

Relevant code:

| File | Lines | What it does |
|---|---|---|
| `frontend/src/app/(auth)/signup/page.tsx` | 32–36 | `signUp` with `emailRedirectTo` |
| `frontend/src/app/(auth)/forgot-password/page.tsx` | 24–26 | `resetPasswordForEmail` with `redirectTo` |
| `frontend/src/app/auth/callback/route.ts` | 5–17 | **the only** link handler: needs `?code=`, PKCE exchange |
| `docs/deployment.md` | Supabase auth settings | `site_url`, `uri_allow_list` |

### R1 — There is no handler for `token_hash`, so any non-PKCE link dies *(root cause)*

`route.ts` reads **only** `searchParams.get("code")` (line 7). If the link arrives
in any other shape, `code` is `null` and it falls straight to line 16:

```ts
return NextResponse.redirect(`${origin}/login?error=${encodeURIComponent("The link is invalid or has expired.")}`);
```

and the login page displays `error` verbatim (`login/page.tsx:23`,
`useState(params.get("error"))`). **That string is exactly what you saw** — so this
branch was taken. There are three normal ways to land in it:

1. Supabase's **default email template** produces `{{ .ConfirmationURL }}` which has
   `?token=…&type=signup`, not `?code=…`. Many projects (and the built-in template)
   end up here.
2. The `code_verifier` **PKCE cookie is gone** — you opened the link in a different
   browser/device/tab, or the cookie expired. Exchange then fails silently and you
   get the same message.
3. Supabase already redirected you once (see R3), so `code` was consumed.

**Fix (robust, cookie-free):** accept `token_hash` and verify server-side. This
works on any device and any browser, and does not depend on a PKCE cookie.

```ts
// src/app/auth/callback/route.ts
const code = searchParams.get("code");
const tokenHash = searchParams.get("token_hash");
const type = searchParams.get("type");

if (code) {
  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (!error) return NextResponse.redirect(`${origin}${next}`);
} else if (tokenHash && type) {
  const { error } = await supabase.auth.verifyOtp({ token_hash: tokenHash, type });
  if (!error) return NextResponse.redirect(`${origin}${next}`);
}
```

…plus, in the Supabase dashboard → Authentication → Email Templates, change the
Confirmation / Recovery links to:
`{{ .SiteURL }}/auth/callback?token_hash={{ .TokenHash }}&type=email&next=/dashboard`
(use `type=recovery&next=/reset-password` for recovery).

### R2 — The 6-digit code (`{{ .Token }}`) has no UI at all

If your project's template sends a **number** instead of a link (Supabase's
"MAGIC LINK / OTP" template style), there is no screen that accepts it:
`grep -rn "verifyOtp\|token_hash" frontend/src` → **nothing**. A user with a code in
the email has literally no way to complete signup. You must add a "enter the
6-digit code" input calling `supabase.auth.verifyOtp({ email, token, type: 'signup' })`.

### R3 — Nothing links `localhost`/preview origin ↔ Supabase `site_url`; the dashboard is authoritative

`emailRedirectTo` sends `window.location.origin` (e.g. `http://localhost:3000` or
your `https://3000-xxxx.e2b.app` preview). But Supabase **ignores any
`redirect_to` that is not in the Redirect allow-list** and falls back to
**`site_url`**. So:

- running locally while `site_url` is the Vercel URL → the link goes to production,
  you land on the production login page logged-out ⇒ "I can't log in";
- `site_url` is still `http://localhost:3000` per `docs/deployment.md` → opening the
  mail on your phone sends you to a URL that does not exist on the phone ⇒ looks
  "expired / no longer exists".

**Check this first.** Supabase → Authentication → URL Configuration:
- `Site URL` = the URL you are actually testing
- `Redirect URLs` must include **every** origin you use:
  `http://localhost:3000/auth/callback`, `https://<preview>.e2b.app/auth/callback`,
  `https://<vercel-web>/auth/callback`

### R4 — Re-signing up silently invalidates the previous link

Every `signUp` for the same unconfirmed email issues a **new** confirmation token and
the old one stops working (`otp_expired`). If you hit "Sign up" twice, or the
mailer is slow and you retried, the link you kept is already dead ⇒ "expired".

### R5 — The built-in Supabase mailer is rate-limited (~a few per hour on free)

`docs/deployment.md` already admits this ("about 2 emails per hour … configure
custom SMTP before real users"). Consequences you will see:

- link never arrives, you retry, the earlier link gets invalidated by R4;
- the retry is **rejected by the mailer limit**, but the page still shows
  "check your email" (`signup/page.tsx:40` sets `sent` regardless) ⇒ a silent
  dead end. You cannot log in and get no error to act on.

### R6 — No "resend confirmation" anywhere

`grep -rn "resend" frontend/src` → **nothing**. Once a link is dead, the user has
**no supported recovery path** from inside the app (nothing calls
`supabase.auth.resend({ type: 'signup', email })`). This is why it feels like
"I must change tab / go there again" — you are improvising a recovery the app does
not offer.

### R7 — Hard-coded stale project in the env templates *(very likely your case)*

`frontend/.env.example` and `backend/.env.example` ship a real project ref and key
from the previous session:

```
NEXT_PUBLIC_SUPABASE_URL=https://tfcwyccbhspkxfttfefc.supabase.co
SUPABASE_URL=https://tfcwyccbhspkxfttfefc.supabase.co
```

If you copied those files to `.env.local` / `.env` you are talking to a project you
may not own (or which may be paused) while the mail goes out with **that** project's
`site_url` and allow-list. Symptoms: mails never arrive, links point at the wrong
domain, and the session cookie never lands ⇒ login impossible no matter what you do
in the UI.

### 1b. What "working email confirmation" must look like (acceptance list)

- [ ] `?code=` **and** `?token_hash=` both work in `/auth/callback`.
- [ ] Opening the link on a **different device** still signs you in.
- [ ] 6-digit code entry exists (if the template sends a code).
- [ ] "Resend confirmation email" button with cooldown + honest rate-limit message.
- [ ] Expired/used links show **which** case it is, plus a "send me a new link" action
      — never a dead-end message.
- [ ] Redirect allow-list includes local, preview and production origins.
- [ ] Custom SMTP configured before showing the app to anyone else.

> Good news: **your `cookies()` + `NextResponse.redirect()` pattern is safe** — I
> probed it on the running dev server and the `Set-Cookie` header survives the 307.
> So once the above is fixed, the session will actually stick.

---

## 2. Other major bugs (reproduced or proven in code)

| # | Bug | Impact | Where | Fix |
|---|---|---|---|---|
| **B1** | **HEIC photos are rejected.** The "Take photo" input uses `accept="image/*"`; iPhone default format is HEIC → backend sniffs magic bytes, fails, returns `415 unsupported_type`. *(Verified: `validate_image_bytes(heic, "image/heic", …)` → `415 unsupported_type`.)* | A large share of real phone users cannot analyse a photo at all. | `frontend/src/app/analyze/page.tsx:77-78`, `backend/app/utils/validators.py:29-33`, `frontend/src/lib/validation.ts` | Re-encode to JPEG client-side via `createImageBitmap` (already used in `lib/image.ts`, it just returns the original on `catch`); or add HEIC support server-side. |
| **B2** | **Avatar storage path mismatch.** Frontend uploads `${uid}/avatar.jpg\|png\|webp`; `is_owned_storage_path()` only accepts `${uid}/avatar-[0-9a-f]{8}\.jpg`. *(Verified: all three frontend paths return `False`.)* | `DELETE /account` never removes the avatar → orphaned personal data after "delete my account" (privacy bug), and the path is never validated. | `frontend/src/app/settings/page.tsx:80` vs `backend/app/utils/validators.py:86` | Agree on one scheme, fix the regex, add a unit test. |
| **B3** | **`model_metrics` table has no writer.** Table + public read policy exist; nothing inserts. The 3 rows were typed in by hand. | The "accuracy per model version" story in the DB is unmaintainable and already unverifiable. | `supabase/migrations/…sql:109-129` | Add `ml/scripts/publish_metrics.py` (service role) upserting `ml/reports/*/evaluation.json`. |
| **B4** | **Deployment bundle pins a commit that does not exist.** `deploy/vercel/api/index.py` + `web/fetch_source.sh` download `…/archive/2e2567245aca…` / `b4824e27…`; `git cat-file -t 2e256724…` → *"no such commit"*. | The documented Vercel deploy would 404 on first cold start (i.e. the API never boots). | `deploy/vercel/*` | Regenerate with `scripts/make_vercel_deploy.py` after pushing, or connect Vercel to GitHub and delete `deploy/vercel/`. |
| **B5** | **Stale docs act as wrong instructions.** `docs/implementation_plan.md` says Phase 1 "in progress", Phase 3/5 "not started" (all done). `docs/deployment.md` / `project_tracking.md` point at the old project + old Vercel URLs, and describe an `site_url` that no longer matches. | Anyone following the docs configures Supabase wrongly — which is R3/R7 again. | `docs/*` | Rewrite from `docs/roadmap.md`; make env/URL setup a checklist. |
| **B6** | **Dev dependencies are broken on a clean clone.** `backend/tests/conftest.py:46` imports `onnx`, `requirements-dev.txt` does not list it. | `pytest` aborts during collection (`ModuleNotFoundError`), so "50 tests pass" is not reproducible by a reviewer. | `backend/requirements-dev.txt` | Add `onnx>=1.16` (or skip the fixture gracefully). |
| **B7** | **History-opened results lose the uncertainty reasons.** `fromDetail()` sets `reasons: []`, but `is_confident` can still be `false` → banner shows with no explanation chips. | Inconsistent UI between "just analysed" and "re-opened", weakens the "honest uncertainty" claim the project is built on. | `frontend/src/components/result/view-model.ts`, `backend/app/services/history_service.py` | Store/derive `uncertainty_reasons` in the detail endpoint. |
| **B8** | **Detail endpoint can 500 on an unexpected category.** `knowledge.guidance_for()` indexes `kb["categories"][category]` with no guard while the schema forces a 7-value Literal. | A legacy/renamed row ⇒ 500 instead of a clean error. | `backend/app/services/history_service.py:get_detail` → `services/knowledge.py:26` | Guard + fallback, or validate on read. |
| **B9** | **No CI at all.** No `.github/`, so `pytest`, `tsc`, `eslint`, `vitest` and `scripts/sync_shared.py --check` never run automatically. | Regressions (like B2/B7) ship unnoticed; the three knowledge-base copies can silently drift. | repo root | GitHub Actions workflow (all of the above are already green locally, so it will pass immediately). |
| **B10** | **No E2E test of the one flow that is broken.** There is no automated signup→confirm→login→predict→delete test. | This class of bug is exactly what E2E catches; unit tests can't see an email link. | — | Playwright with a seeded user + `admin.generateLink()`. |

---

## 3. Where the project "lags" (performance & robustness, not correctness)

| # | Lag | Reason | Effect |
|---|---|---|---|
| L1 | **Cold-start ~3.5 s** on serverless | ONNX model (13.9 MB) + a lazy commit-archive download+extract per instance | First scan after idle feels broken; keep-alive or bake artefacts into the image. |
| L2 | **Rate limiting is per-process memory** (`utils/rate_limit.py`) | `defaultdict` in RAM | On serverless each instance counts separately ⇒ the 10/min & 300/day limits are effectively much higher. |
| L3 | **Analytics pulls up to 5,000 rows into Python** then aggregates (`analytics_service.MAX_ROWS`) | no SQL aggregate/RPC view | Slow and memory-hungry for heavy users; silently `truncated` above 5,000. Move to a Postgres view/RPC. |
| L4 | **Every page refetches with `cache: "no-store"`** (`lib/api.ts`) | no SWR/react-query | Dashboard→Analyze→Result repeats the same calls; visible spinner churn. |
| L5 | **Heavy client bundles**: `/analytics` 346 kB, `/result/[id]` 246 kB first-load | Recharts + all of `lucide-react` | Slow on 3G/4G phones — the exact audience. Dynamic-import charts. |
| L6 | **No request timeout/retry UX** beyond `ApiError` mapping | single `fetch` | On a flaky network the scan button just spins. |
| L7 | **`model_metrics` / analytics are never cached**; `/health` reloads model check every call | — | unnecessary work per request. |
| L8 | **No observability** (no Sentry, no metrics) | only `log.info` with request-id | You cannot see that users are failing at the email step — which is why this bug survived. |
| L9 | **No storage sweeper** | only per-request compensation on insert failure | Orphans accumulate (worse because of B2). |
| L10 | **`.env.example` doubles as config** | real project ref committed | Guarantees R7 for anyone who copies it. |

---

## 4. Fix order (what I would do, in order)

**Step 1 — unblock login (½ day).** R1 + R2 + R6 in the auth flow; R3 + R7 as
configuration; then R4/R5 messaging. Deliverable: signup on any device, any browser,
with a working resend, and a truthful error when a link is genuinely dead.

**Step 2 — stop the silent data loss (¼ day).** B2 (avatar regex), B7 (reasons),
B8 (guard), B6 (`onnx` dev dep).

**Step 3 — make it verifiable (½ day).** B9 CI + B10 Playwright signup→login→predict
E2E. After this, this class of bug cannot come back unnoticed.

**Step 4 — deployment truth (¼ day).** B4 regenerate the deploy bundle, B5 rewrite
the docs from `docs/roadmap.md`, publish B3 metrics.

**Step 5 — real-world media + scale.** B1 (HEIC), then L1–L5.

---

### TL;DR

- The email link handler understands **one** URL shape (`?code=`) and everything
  else becomes the hard-coded string *"The link is invalid or has expired."* — no
  `token_hash`, no 6-digit code, no resend. **That is your bug.**
- Second most likely cause: the app points at **someone else's Supabase project**
  (hard-coded in `.env.example`) with a `site_url`/allow-list that does not include
  the origin you are testing ⇒ Supabase silently redirects the link to the wrong
  host, or consumes it and the exchange fails.
- The app itself (model, API, UI) is healthy: production `next build` succeeds, 45
  backend tests pass, the real ONNX model predicts correctly in 5.4 ms.
