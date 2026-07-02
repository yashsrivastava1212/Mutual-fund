# Deployment Guide

Deploy the **backend (FastAPI + LanceDB + scheduler)** on [Railway](https://railway.app) and the **frontend (static UI)** on [Vercel](https://vercel.com).

Repository: [yashsrivastava1212/Mutual-fund](https://github.com/yashsrivastava1212/Mutual-fund)

---

## Architecture (split deploy)

```
Browser
   │
   ▼
Vercel (ui/) ── rewrite /api/* ──► Railway (FastAPI + LanceDB volume)
                                         │
                                         ├── Groq API (LLM)
                                         └── Groww (daily ingestion)
```

| Component | Platform | URL example |
|-----------|----------|-------------|
| Frontend | Vercel | `https://mutual-fund.vercel.app` |
| Backend API | Railway | `https://mutual-fund-api.up.railway.app` |

The UI uses relative paths (`/api/chat`, `/api/corpus`). Vercel **rewrites** proxy those requests to Railway so the browser stays same-origin and CORS stays simple.

---

## Prerequisites

1. GitHub repo connected to Railway and Vercel
2. [Groq API key](https://console.groq.com) (`GROQ_API_KEY`)
3. Railway plan with **persistent volume** (LanceDB lives on disk under `data/`)
4. Railway service with **≥ 2 GB RAM** recommended (BGE embedding model loads in memory on first retrieval/ingestion)

---

## Part 1 — Backend on Railway

### 1.1 Create the service

1. Go to [Railway](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select `yashsrivastava1212/Mutual-fund`
3. Railway detects the `Dockerfile` — use **Docker** build (recommended)

### 1.2 Start command

Railway injects a dynamic `PORT`. Override the default Docker CMD in **Settings → Deploy → Start Command**:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### 1.3 Persistent volume (required)

Without a volume, LanceDB and ingestion data are lost on every redeploy.

1. **Service → Volumes → Add Volume**
2. Mount path: `/app/data`
3. Redeploy after attaching the volume

This maps to `data/index/lancedb`, `data/raw/`, and `data/processed/` in the app.

### 1.4 Environment variables

In **Railway → Variables**, set:

| Variable | Value | Required |
|----------|-------|----------|
| `GROQ_API_KEY` | Your Groq key | Yes |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | No |
| `GROQ_TIMEOUT_SECONDS` | `120` | No |
| `GROQ_MAX_TOKENS` | `512` | No |
| `GROQ_TEMPERATURE` | `0.1` | No |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | No |
| `MAX_MESSAGE_LENGTH` | `2000` | No |
| `RATE_LIMIT_REQUESTS` | `30` | No |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | No |
| `SCHEDULER_ENABLED` | `true` | Recommended |
| `SCHEDULER_HOUR` | `10` | No |
| `SCHEDULER_MINUTE` | `0` | No |
| `SCHEDULER_TIMEZONE` | `Asia/Kolkata` | No |
| `SCHEDULER_MAX_RETRIES` | `2` | No |
| `SCHEDULER_RETRY_DELAY_SECONDS` | `60` | No |

Do **not** commit `.env` to GitHub. Set secrets only in Railway.

### 1.5 Health check

**Settings → Deploy → Health Check Path:**

```
/health
```

Expected response:

```json
{
  "status": "ok",
  "llm_configured": true,
  "corpus_schemes": 5
}
```

Note: `corpus_schemes` is always `5` from config; chat will not work until the index is built (step 1.7).

### 1.6 Generate public URL

**Settings → Networking → Generate Domain**

Example: `https://mutual-fund-api.up.railway.app`

Save this URL — you need it for Vercel rewrites.

### 1.7 First-time index build

After the first deploy (with volume attached), run ingestion once:

**Option A — Railway shell (one-off)**

```bash
python -m scheduler.daily --run-now
```

**Option B — Local against Railway** (not typical)

Use Railway CLI or trigger via a temporary deploy command override.

Ingestion fetches 5 Groww pages, embeds 51 chunks, and writes LanceDB to `/app/data/index/lancedb`. Expect **2–5 minutes** on first run (model download + embed).

Verify:

```bash
curl https://YOUR-RAILWAY-URL.up.railway.app/health
curl https://YOUR-RAILWAY-URL.up.railway.app/api/scheduler/status
```

### 1.8 Daily scheduler on Railway

With `SCHEDULER_ENABLED=true`, the FastAPI process starts an APScheduler cron job at **10:00 AM IST** (`Asia/Kolkata`).

**Alternative:** add a second Railway service from the same repo with start command:

```bash
python -m scheduler.daily --daemon
```

If you use a dedicated scheduler service, set `SCHEDULER_ENABLED=false` on the API service to avoid duplicate runs.

### 1.9 Test the API

```bash
curl -X POST https://YOUR-RAILWAY-URL.up.railway.app/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"What is the expense ratio of HDFC Mid Cap Fund Direct Growth?\"}"
```

---

## Part 2 — Frontend on Vercel

### 2.1 One-line UI fix for Vercel

When served from FastAPI locally, the UI loads JS from `/ui/app.js`. On Vercel the `ui/` folder is the site root, so use a relative script path.

In `ui/index.html`, change:

```html
<script src="/ui/app.js" defer></script>
```

to:

```html
<script src="./app.js" defer></script>
```

> **Local dev:** FastAPI still serves the UI at `GET /` with `/ui/app.js`. After this change, run locally with `uvicorn` and open `http://localhost:8000/ui/index.html` for UI testing, or temporarily revert the script path. Alternatively, add a FastAPI route that serves `app.js` at `/app.js` if you want both hosts to work without edits.

### 2.2 Create `ui/vercel.json`

Create this file in the repo (commit and push):

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://YOUR-RAILWAY-URL.up.railway.app/api/:path*"
    }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" }
      ]
    }
  ]
}
```

Replace `YOUR-RAILWAY-URL` with your actual Railway domain from §1.6.

This proxies `/api/chat` and `/api/corpus` from the Vercel origin to Railway. No CORS changes needed in the browser.

### 2.3 Import project on Vercel

1. [Vercel Dashboard](https://vercel.com) → **Add New → Project**
2. Import `yashsrivastava1212/Mutual-fund`
3. **Root Directory:** `ui`
4. **Framework Preset:** Other (static)
5. **Build Command:** leave empty
6. **Output Directory:** `.` (default)
7. Deploy

Vercel assigns a URL like `https://mutual-fund.vercel.app`.

### 2.4 Custom domain (optional)

**Project → Settings → Domains** — add your domain and follow DNS instructions.

Update `ui/vercel.json` if you change the Railway backend URL.

### 2.5 Verify frontend

1. Open your Vercel URL
2. Confirm the scheme watchlist loads (calls `/api/corpus` via rewrite)
3. Ask: *"What is the expense ratio of HDFC Mid Cap Fund Direct Growth?"*
4. Expect an answer with citation link and last-updated footer

---

## Part 3 — Post-deploy checklist

| Check | How |
|-------|-----|
| Backend health | `GET /health` → `status: ok`, `llm_configured: true` |
| Index built | `GET /api/scheduler/status` → `last_success` populated |
| Chat works | POST `/api/chat` with a factual question |
| Scheduler | `next_schedule` shows `10:00 Asia/Kolkata` |
| Frontend → API | Vercel UI loads schemes and returns chat replies |
| Secrets | `.env` not in Git; keys only in Railway/Vercel |

---

## Troubleshooting

### Chat returns empty or “no information”

- Index not built — run `python -m scheduler.daily --run-now` on Railway
- Volume not mounted — LanceDB wiped on redeploy; attach `/app/data` volume

### 502 / timeout on Railway

- First request after cold start loads the embedding model — can take 30–60s
- Increase service memory to 2 GB+
- Increase Railway request timeout if available

### Vercel UI loads but watchlist is empty

- Check `ui/vercel.json` rewrite URL matches Railway domain (include `https://`, no trailing slash)
- Open browser DevTools → Network → confirm `/api/corpus` returns 200

### CORS errors

- Backend already allows `allow_origins=["*"]` in `app/main.py`
- Prefer Vercel rewrites (same-origin) instead of calling Railway URL directly from JS

### Rate limit (429)

- Default: 30 requests / 60s per IP
- Adjust `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS` on Railway

### Scheduler did not run

- Confirm `SCHEDULER_ENABLED=true` on the API service (or dedicated scheduler service running)
- Check `GET /api/scheduler/status` for `last_error`
- Railway free tier may sleep services — use a paid plan or external cron hitting a health endpoint

---

## Environment summary

| Where | What to set |
|-------|-------------|
| Railway | All backend vars (`GROQ_API_KEY`, scheduler, rate limits) |
| Vercel | No secrets required if using rewrites; backend URL only in `ui/vercel.json` |
| GitHub | Never commit `.env` or API keys |

---

## Quick reference

```bash
# Railway — health
curl https://YOUR-RAILWAY-URL.up.railway.app/health

# Railway — manual ingestion (shell)
python -m scheduler.daily --run-now

# Local — full stack (combined UI + API)
uvicorn app.main:app --reload
# → http://localhost:8000
```

---

## Related docs

- [README.md](README.md) — local setup and API reference
- [content/Architecture.md](content/Architecture.md) — system design
- [content/ImplementationPlan.md](content/ImplementationPlan.md) — build phases
