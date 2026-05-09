# Deploying DocuMate from scratch

A complete walkthrough for standing up DocuMate end-to-end: local setup, corpus build, deploy to Fly.io + Vercel, and verification. Written for someone (including future me) coming to the repo cold.

If you only want to run it locally, you can stop after [Local development](#3-local-development).

---

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [Local setup](#2-local-setup)
3. [Local development](#3-local-development)
4. [Building the corpus](#4-building-the-corpus)
5. [Running the eval suite](#5-running-the-eval-suite)
6. [Deploying the backend to Fly.io](#6-deploying-the-backend-to-flyio)
7. [Deploying the frontend to Vercel](#7-deploying-the-frontend-to-vercel)
8. [Wiring the two together](#8-wiring-the-two-together)
9. [Verifying the deployed app](#9-verifying-the-deployed-app)
10. [Operating the deployment](#10-operating-the-deployment)
11. [Common issues and fixes](#11-common-issues-and-fixes)
12. [Cost expectations](#12-cost-expectations)
13. [Tearing it down](#13-tearing-it-down)

---

## 1. Prerequisites

### Tools (install once)

| Tool      | Min version | Why                                  | Install                                                                |
|-----------|-------------|--------------------------------------|------------------------------------------------------------------------|
| Python    | 3.11        | Backend runtime                      | `brew install python@3.11` or use [pyenv](https://github.com/pyenv/pyenv) |
| uv        | 0.5+        | Python package + venv manager        | `curl -LsSf https://astral.sh/uv/install.sh \| sh`                     |
| Node.js   | 20          | Frontend runtime                     | `brew install node@20` or [nvm](https://github.com/nvm-sh/nvm)         |
| pnpm      | 9+          | Frontend package manager             | `corepack enable pnpm` (ships with Node 20)                            |
| Git       | any         | Cloning, committing                  | preinstalled on macOS                                                  |
| Make      | any         | Task runner                          | preinstalled on macOS                                                  |
| Fly CLI   | 0.3+        | Backend deploy                       | `curl -L https://fly.io/install.sh \| sh`                              |
| Vercel CLI| 38+         | Frontend deploy (optional, GitHub integration is the alternative) | `pnpm add -g vercel`                |

Verify:

```bash
python3.11 --version
uv --version
node --version
pnpm --version
fly version
vercel --version
```

### Accounts (free tiers are sufficient)

- **Anthropic** — needed for the generator + judge. Sign up at https://console.anthropic.com and create an API key. Generator uses `claude-sonnet-4-6`, judge uses `claude-haiku-4-5-20251001`. Budget ~US$2-5 to run the full eval suite once.
- **Fly.io** — backend host. https://fly.io/app/sign-up. Add a credit card; you won't be charged on the hobby tier provided machines auto-stop (they will).
- **Vercel** — frontend host. https://vercel.com/signup. Hobby tier is free.
- **GitHub** — repo hosting. Vercel auto-imports from GitHub.

### Repo

```bash
git clone https://github.com/<your-handle>/DocuMate.git
cd DocuMate
```

---

## 2. Local setup

### 2.1 Install dependencies

```bash
make install
```

This runs `uv sync` in `backend/` and `pnpm install` in `frontend/`. First run takes a few minutes — uv downloads ~600 MB (PyTorch + sentence-transformers).

### 2.2 Create your `.env`

```bash
cp .env.example .env
```

Open `.env` and fill in:

```bash
ANTHROPIC_API_KEY=sk-ant-...   # required, from console.anthropic.com
```

The other values have sensible defaults. Don't change `ANTHROPIC_GENERATOR_MODEL` or `ANTHROPIC_JUDGE_MODEL` unless you understand the model-name contract documented in [CLAUDE.md](../CLAUDE.md).

### 2.3 Verify the toolchain

```bash
make test   # runs backend/tests/, expects 83 passing
```

If tests pass you're set. If they fail before you've changed anything, your environment is broken — most likely Python version. Check with `cd backend && uv run python --version` (must be 3.11.x).

---

## 3. Local development

You need three terminals.

### Terminal 1: Backend

```bash
make backend
```

Starts FastAPI on `http://localhost:8000`. First request takes ~6s while sentence-transformers loads the BGE model into memory; subsequent requests are fast.

### Terminal 2: Frontend

```bash
make frontend
```

Starts Next.js on `http://localhost:3000`. The frontend's `app/api/chat/route.ts` proxies to `http://127.0.0.1:8000` by default.

### Terminal 3: ad-hoc curls / git / etc.

Quick smoke test (won't work until you've done [section 4](#4-building-the-corpus)):

```bash
curl http://localhost:8000/health
# {"status":"ok","collection_size":145,...}

curl -X POST http://localhost:8000/chat \
  -H "content-type: application/json" \
  -d '{"query":"What notice do I give when resigning?"}'
```

Open http://localhost:3000 — chat UI should load.

---

## 4. Building the corpus

If `data/processed/` already has 60 markdown files committed (it should, the repo includes them), skip 4.1 and run 4.2 directly.

### 4.1 (Re-)scrape Fair Work content

```bash
make scrape
```

Crawls https://fairwork.gov.au from the seed URLs in [backend/scripts/sources.yaml](../backend/scripts/sources.yaml), one level deep, at 1 req/sec, using a Chrome user-agent (their WAF silently drops anything else). Output:

- `data/raw/{slug}.html` — raw HTML, gitignored
- `data/processed/{slug}.md` — extracted markdown with YAML frontmatter, committed
- `data/processed/manifest.json` — corpus lockfile, committed

The scrape takes ~2 minutes and is idempotent (skips URLs already in the manifest unless you pass `--force`).

### 4.2 Build the Chroma index

```bash
make ingest
```

Reads `data/processed/manifest.json`, chunks each doc (recursive splitter, 500 token target with 50 overlap, measured by tiktoken `cl100k_base`), embeds with BGE-small-en-v1.5, and upserts to ChromaDB at `data/chroma/`.

Expected output: ~145 chunks, ~53k tokens, ~20 seconds of wall time after the first run (first run downloads the BGE model, ~130 MB).

Verify:

```bash
make verify-ingest
```

Top-3 results for a sanity query — the first one must come from a notice/termination doc. If it doesn't, the BGE query prefix is broken; see [embedder.py](../backend/app/services/embedder.py).

---

## 5. Running the eval suite

The eval framework is the whole reason this project exists. Running it tests that retrieval, generation, and the LLM-as-judge are all wired up correctly.

### 5.1 Baseline

```bash
make eval
```

Loads [backend/evals/configs/baseline.yaml](../backend/evals/configs/baseline.yaml) and runs all 30 entries from [backend/evals/dataset.yaml](../backend/evals/dataset.yaml) through the same `ChatService` pipeline the API uses. Writes:

- `backend/evals/reports/baseline_<timestamp>.json` — per-case raw results
- `backend/evals/reports/baseline_<timestamp>.md` — human-readable summary

Total runtime: ~5-8 minutes. Anthropic spend: ~US$0.50-1.00 (30 generator calls + 30 Haiku judge calls).

### 5.2 With cross-encoder reranking

```bash
make eval-rerank
```

Loads [backend/evals/configs/reranked.yaml](../backend/evals/configs/reranked.yaml) and emits a markdown report that includes a baseline-vs-reranked diff table. First run downloads the BAAI/bge-reranker-base weights (~440 MB).

The decision on whether to keep reranking on by default is in [docs/decisions/0002-reranking.md](decisions/0002-reranking.md).

---

## 6. Deploying the backend to Fly.io

### 6.1 Auth and create the app

```bash
fly auth login
fly apps create documate-api -c infra/fly.toml
```

If you want a different app name, edit `app = "..."` in [infra/fly.toml](../infra/fly.toml) before running `fly apps create`.

### 6.2 Set secrets

Generate the demo key first so you have it for the Vercel side:

```bash
DEMO_KEY=$(openssl rand -hex 16)
echo "$DEMO_KEY"   # save this somewhere safe; Fly never reveals secret values after set

fly secrets set -c infra/fly.toml \
  ANTHROPIC_API_KEY=sk-ant-... \
  CORS_ALLOWED_ORIGINS=https://your-vercel-domain.vercel.app \
  DEMO_KEY=$DEMO_KEY
```

Critical:

- **No trailing slash** on `CORS_ALLOWED_ORIGINS`. The browser sends `Origin: https://...vercel.app` (no slash) and FastAPI's CORS middleware does an exact match.
- **Always pass `-c infra/fly.toml`** — `fly` looks for `fly.toml` in the current dir, ours lives at `infra/`.
- If you don't yet have the Vercel domain (because Vercel deploys after Fly), put a placeholder like `https://placeholder.vercel.app` and update it after the Vercel deploy succeeds.
- Don't paste the API key into chat tools, screen-shares, or anywhere it gets logged. If it leaks, rotate at https://console.anthropic.com/settings/keys.

### 6.3 Deploy

```bash
make deploy-api
```

This runs `fly deploy --config infra/fly.toml --dockerfile infra/Dockerfile`.

First deploy takes 8-12 minutes because the multi-stage Dockerfile pre-downloads:

- BGE-small embedder weights (~130 MB)
- bge-reranker-base weights (~440 MB)
- The full `data/chroma/` directory (the vector store is **baked into the image**, not mounted as a volume)

Subsequent deploys are faster (~2-3 min) because Docker layer caching skips the model downloads when their layers haven't changed.

### 6.4 Reduce to a single machine

By default `fly deploy` provisions 2 machines for HA. For a portfolio demo, one is plenty:

```bash
fly scale count 1 -c infra/fly.toml
```

Combined with `auto_stop_machines = "stop"` in `fly.toml`, the single machine idles to zero a few minutes after the last request, so steady-state cost is ~$0/month.

### 6.5 Verify

```bash
fly status -c infra/fly.toml
# Should show: 1 machine, started, healthy

curl -s https://documate-api.fly.dev/health
# Should return: {"status":"ok","collection_size":145,...}
```

If `/health` returns 200, the backend is live. The "Proxy is having trouble reaching app" banner in the Fly dashboard often shows during the first ~30s after deploy — it's stale once `/health` works.

---

## 7. Deploying the frontend to Vercel

Two paths: GitHub auto-import (easier, recommended) or `vercel` CLI. The instructions below cover GitHub auto-import; CLI is at the bottom.

### 7.1 Auto-import from GitHub

1. Push your repo to GitHub if you haven't already.
2. Go to https://vercel.com/new and click **Import** next to your DocuMate repo.
3. **Critical settings on the New Project screen:**
   - **Root Directory:** click **Edit** and change `./` to `frontend`. The "Application Preset" should auto-flip from "Services" to **Next.js**.
   - **Build/Output/Install commands:** leave blank. Vercel auto-detects `next build`, `.next`, and `pnpm install` from `pnpm-lock.yaml`.
   - **Environment Variables:** leave empty for now. You'll add them after the first deploy.
4. Click **Deploy**.

The first deploy will succeed but `/api/chat` will return 502 ("Backend unreachable") because `API_URL` isn't set. Expected — fix in section 8.

### 7.2 Add environment variables

After the deploy completes, note the production URL (e.g. `https://documate-eta.vercel.app`).

Go to **Project Settings → Environment Variables** and add:

| Key        | Value                                       | Environments               | Notes                                      |
|------------|---------------------------------------------|----------------------------|--------------------------------------------|
| `API_URL`  | `https://documate-api.fly.dev` (no slash)   | Production, Preview        | Server-side only; do NOT mark "Expose to client" |
| `DEMO_KEY` | The hex string from `openssl rand` earlier  | Production, Preview        | Server-side only                           |

Trigger a redeploy — Settings → Deployments → click `⋯` on the latest → **Redeploy**. Or push any commit.

### 7.3 Alternative: CLI

```bash
cd ~/Development/DocuMate
vercel link                   # link to an existing Vercel project; pick "frontend" as Root Directory
vercel env add API_URL        # paste https://documate-api.fly.dev
vercel env add DEMO_KEY       # paste the demo key
make deploy-web               # runs `vercel --prod` from the repo root
```

The Makefile target runs `vercel --prod` from the **repo root** deliberately. Don't `cd frontend && vercel --prod` — that resolves to `frontend/frontend` and fails because the linked project's Root Directory is already `frontend`.

---

## 8. Wiring the two together

If you used a placeholder for `CORS_ALLOWED_ORIGINS` during the Fly deploy, update it now with the real Vercel domain:

```bash
fly secrets set -c infra/fly.toml \
  CORS_ALLOWED_ORIGINS=https://documate-eta.vercel.app
```

Setting a secret on Fly automatically rolls the running machines so the new value takes effect.

If you have multiple Vercel preview URLs you want to allow (e.g. branch deploys), pass them comma-separated:

```bash
CORS_ALLOWED_ORIGINS=https://documate-eta.vercel.app,https://documate-preview.vercel.app
```

---

## 9. Verifying the deployed app

### 9.1 Backend smoke test

```bash
# Health
curl -s https://documate-api.fly.dev/health
# Expect: {"status":"ok","collection_size":145,"generator_model":"claude-sonnet-4-6"}

# Chat (with demo key)
curl -s -X POST https://documate-api.fly.dev/chat \
  -H "content-type: application/json" \
  -H "x-demo-key: <YOUR_DEMO_KEY>" \
  -d '{"query":"What notice do I give when resigning after 4 years?"}' | jq
# Expect: structured JSON with answer, citations, retrieved_chunk_ids, latency_ms

# Demo key gate (without the header — must 401)
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://documate-api.fly.dev/chat \
  -H "content-type: application/json" \
  -d '{"query":"x"}'
# Expect: 401

# Rate limit (11 rapid requests with the demo key — the 11th must 429)
for i in {1..11}; do
  curl -s -o /dev/null -w "%{http_code} " -X POST https://documate-api.fly.dev/chat \
    -H "content-type: application/json" \
    -H "x-demo-key: <YOUR_DEMO_KEY>" \
    -d '{"query":"x"}'
done
echo
# Expect: 200 200 200 200 200 200 200 200 200 200 429
```

### 9.2 Frontend smoke test

1. Open the Vercel URL in a fresh browser window.
2. Type a question into the composer (the suggested chips are good test cases): "How much notice do I give when resigning after 3 years?"
3. Expect: assistant response within ~5-10s, inline `[1]` `[2]` citations, clickable chips below.
4. Click a citation chip — the right-side drawer should open with title, source URL, and excerpt.
5. Open DevTools → Network → click `/api/chat`. Should be 200, not 502 (502 = `API_URL` is wrong or Fly is down).

### 9.3 Smoke from a different network

The single best test: open the Vercel URL on your phone over LTE (not Wi-Fi). Asks the question, gets an answer. If this works, you've proved end-to-end connectivity from the public internet through Vercel through Fly through Anthropic.

---

## 10. Operating the deployment

### 10.1 Updating the corpus

The Chroma store is baked into the Fly image, not mounted. To update content:

```bash
make scrape       # only if you want to re-fetch source markdown
make ingest       # rebuilds data/chroma/
make deploy-api   # ships the new image
```

Same flow if you change chunking parameters in `backend/ingest/chunker.py`.

### 10.2 Updating prompts or generation logic

Code changes only — no re-ingest needed:

```bash
git push                         # if you have CI auto-deploy wired up
# OR
make deploy-api && make deploy-web
```

### 10.3 Rotating the Anthropic API key

```bash
# 1. Create a new key in console.anthropic.com
# 2. Set it on Fly
fly secrets set -c infra/fly.toml ANTHROPIC_API_KEY=sk-ant-NEW_KEY
# 3. Revoke the old key in console.anthropic.com
```

The `fly secrets set` rolls machines automatically; no redeploy needed.

### 10.4 Monitoring

- Fly: https://fly.io/apps/documate-api → **Metrics** tab (memory, CPU, request rate). **Logs & Errors** tab for live tail.
- Vercel: https://vercel.com/<team>/documate → **Logs** tab (function logs, including the `/api/chat` proxy).
- Anthropic: https://console.anthropic.com/settings/usage for spend.

### 10.5 Pausing the demo (saving cost without tearing down)

```bash
fly scale count 0 -c infra/fly.toml   # backend goes dark
```

Restart with `fly scale count 1 -c infra/fly.toml`.

The Vercel side keeps serving the static page for free regardless.

---

## 11. Common issues and fixes

| Symptom                                                                       | Cause                                                                                         | Fix                                                                                       |
|-------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------|
| `fly: missing app name` when running secrets/deploy                           | `fly` looks for `fly.toml` in CWD; ours is at `infra/`                                        | Always pass `-c infra/fly.toml` (or `cd infra/`)                                          |
| Frontend shows "Backend unreachable" 502 on `/api/chat`                       | `API_URL` is missing or Fly is down                                                           | Check Vercel env vars; `curl /health` on Fly                                              |
| CORS error in browser console: "Origin ... not allowed"                       | `CORS_ALLOWED_ORIGINS` doesn't include the exact Vercel domain (often a trailing slash)       | `fly secrets set CORS_ALLOWED_ORIGINS=https://...vercel.app` (no slash)                   |
| `/chat` returns 401 "Missing or invalid demo key"                             | `DEMO_KEY` set on Fly but not forwarded by the frontend                                       | Add `DEMO_KEY` to Vercel env vars; redeploy the frontend                                  |
| Vercel deploy fails: `path "...frontend/frontend" does not exist`             | Linked project has Root Directory = `frontend`; running `vercel` from inside `frontend/` doubles it | Run `vercel --prod` from the repo root                                                |
| Vercel auto-import shows "Application Preset: Services" with a `vercel.json` requirement | Vercel detected the monorepo; defaults to deploying both frontend and backend | Set Root Directory = `frontend` on the New Project page; preset switches to "Next.js"     |
| Fly deploy succeeds but logs show httpx requests to `huggingface.co`          | sentence-transformers performs an online ETag check on cached weights by default              | Set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` in `fly.toml [env]` (already done in this repo) |
| Healthcheck fails with `start-period` timeout on first deploy                 | Embedder takes 6-15s to load on cold start, 30s grace was too tight                           | Bumped to 60s `grace_period` in `fly.toml [[http_service.checks]]`                        |
| Fly bills more than expected                                                  | More than 1 machine running, OR auto-stop didn't kick in                                      | `fly scale count 1 -c infra/fly.toml`; verify `auto_stop_machines = "stop"` in fly.toml   |
| `make ingest` takes >5 minutes                                                | First run is downloading BGE model (~130 MB)                                                  | Subsequent runs hit the cache at `~/.cache/huggingface/`; expect ~20s                     |
| pnpm not found                                                                | Node 20 ships with corepack but doesn't enable pnpm by default                                | `corepack enable pnpm`                                                                    |
| Tests fail with `ModuleNotFoundError: No module named 'app'`                  | Running pytest from the repo root instead of `backend/`                                       | Always `cd backend && uv run pytest` (the `make test` target does this)                   |

---

## 12. Cost expectations

Numbers below are May 2026 prices; verify if you're returning later.

| Service     | Free tier reality                                                                              | What this project actually uses                                          |
|-------------|------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| Fly.io      | First $5/month free across the account                                                         | shared-cpu-2x@2GB with auto-stop ≈ $0-2/month at portfolio traffic       |
| Vercel      | Hobby tier: free with bandwidth/build limits                                                   | Static page + 1 serverless function call per chat ≈ free                 |
| Anthropic   | No free tier; pay-per-token                                                                    | ~$0.50-1.00 per full eval run; ~$0.01 per chat answer                    |
| GitHub      | Free for public repos                                                                          | $0                                                                        |
| Hugging Face| Free for public model weights                                                                  | $0 (and model weights are baked into the Fly image, no runtime fetch)    |

**Idle steady-state for this repo: ~$0/month.** The cost only accumulates when someone actually uses the demo.

---

## 13. Tearing it down

```bash
# Backend
fly apps destroy documate-api -y

# Frontend
# Vercel dashboard → Project Settings → bottom of the page → Delete Project

# Local
rm -rf backend/.venv frontend/node_modules frontend/.next data/chroma
```

The repo itself is fine to keep — `git clone` + `make install` reproduces the local environment from scratch.
