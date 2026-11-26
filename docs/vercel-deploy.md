# Deploying WasteWise to Vercel

WasteWise has **two runtimes** that cannot share one Vercel project:

| Part | Runtime | Needs |
|---|---|---|
| **Web** | Next.js 15 (Node 22) | `frontend/` — `package.json`, `next.config.ts` |
| **API** | FastAPI (Python 3.12) | `backend/` — `index.py`, `requirements.txt`, `model_artifacts/` (16 MB ONNX) |

A Vercel project builds **one** app with **one** runtime. So you create **two projects
from the same repository**, and the only setting that differs is the **Root Directory**.

> There is a root `vercel.json` in this repo. It builds the **web app only** (see
> "Path B" below). It cannot deploy the API as well — no single Vercel project can
> host both a Next.js build and a Python function tree.

---

## Path A (recommended): two projects, Root Directory set

### 1. API project

Vercel → **Add New → Project** → import `Deepanshusharma22/Wastewise`

| Setting | Value |
|---|---|
| Root Directory | **`backend`** |
| Framework Preset | **FastAPI** (from `backend/vercel.json`) |
| Entry point | `backend/index.py` (auto-detected) |
| Install / Build | leave empty (Vercel installs `requirements.txt` and runs the Python preset) |
| Region | `bom1` comes from `backend/vercel.json` (Hobby plan may still run it in `iad1`) |

Environment variables (Settings → Environment Variables → Production **and** Preview):

```
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_ANON_KEY=<publishable key>
SUPABASE_SERVICE_ROLE_KEY=<secret key>      # only used by DELETE /account
ENVIRONMENT=production                      # turns /docs off; hides model errors
CORS_ORIGINS=https://<your-web-project>.vercel.app
```

Do **not** set `LOCAL_MODE` (SQLite has no persistent disk on Vercel).

Check: `https://<api>.vercel.app/api/v1/health` → `{"status":"ok","model_loaded":true,...}`.
`backend/.vercelignore` already excludes tests and `.env`, and **keeps**
`model_artifacts/`, so the model is bundled and loads without any download.

### 2. Web project

Vercel → **Add New → Project** → import the **same** repo again

| Setting | Value |
|---|---|
| Root Directory | **`frontend`** |
| Framework Preset | Next.js (auto-detected) |
| Build / Install | defaults (`next build`, `npm ci` with the committed lockfile) |

```
API_URL=https://<api>.vercel.app          # read at BUILD time by next.config.ts rewrites
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<publishable key>
```

`API_URL` is baked in at build time — after changing it you must **redeploy**.

### 3. Supabase (this is what made login fail before)

Authentication → URL Configuration:

- **Site URL** = `https://<web>.vercel.app`
- **Redirect URLs** must include:
  - `https://<web>.vercel.app/auth/callback`
  - `http://localhost:3000/auth/callback`
  - any preview domain you test on

If the redirect URL is missing, Supabase ignores `emailRedirectTo` and falls back to
`Site URL`; the confirmation link then lands on the wrong host and fails.

Also: Authentication → SMTP — the built-in mailer allows ~2 messages per hour, so
sign-ups look broken until you configure your own provider.

Optional but more robust for e-mail links (works on any device, no PKCE cookie):
Authentication → Email Templates → Confirmation / Recovery →
`{{ .SiteURL }}/auth/callback?token_hash={{ .TokenHash }}&type=email&next=/dashboard`
(use `type=recovery&next=/reset-password` for recovery).

---

## Tried and rejected: a `vercel.json` at the repository root

We added a root `vercel.json` (`framework: nextjs`, `installCommand: cd frontend && npm ci`,
`buildCommand: cd frontend && npm run build`, `outputDirectory: frontend/.next`) and
pushed it. **Result: the project `deepanshu-projects1/wastewise` deployment failed**
(commit `89fbe7e`), while the base commit had deployed successfully.

Both commands work locally, so the failure comes from Vercel's Next.js builder wanting the
app (its `package.json` and `node_modules`) at the *project* root — a `cd frontend` wrapper
does not satisfy it. The file was therefore removed.

**Conclusion: do not put a `vercel.json` at the repo root for this layout. Set the
project's Root Directory to `frontend` instead** (Path A step 2). `backend/vercel.json`
stays, because there the Root Directory *is* `backend`.

---

## Legacy: do not use `deploy/vercel/`

`deploy/vercel/{web,api}` are bootstrap stubs from an earlier "upload files, download a
pinned commit archive" workaround. Their pinned commits never existed in this repository
and the API stub's checksum is intentionally empty, so it refuses to start. Git import
(Path A) replaces them entirely; the folder can be deleted once the projects are set up.

---

## Cost / behaviour notes

- **Cold start:** the API loads the 14 MB ONNX model lazily on the first request to each
  instance — expect ~3.5 s after idle, single-digit ms when warm.
- **Uploads:** Vercel caps request bodies at 4.5 MB, so the API enforces 4 MB and the web
  app downscales phone photos in the browser (and converts HEIC/HEIF to JPEG) first.
- **Rate limits** are held in process memory, so on serverless they are per instance.
