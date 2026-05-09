# Architecture

![DocuMate architecture: browser → Vercel (Next.js) → Fly.io (FastAPI) → Retriever → ChromaDB + optional cross-encoder reranker → Generator → Anthropic API](diagrams/architecture.png)

## Components at a glance

```
  Source docs (Fair Work HTML)
            │
            ▼
     ┌──────────────┐     ┌────────────────────┐     ┌────────────┐
     │  Ingestion   │────▶│  Embedder          │────▶│ ChromaDB   │
     │  (batch CLI) │     │  (BGE-small, CPU,  │     │ (file-     │
     │              │     │   sentence-trans.) │     │  backed)   │
     └──────────────┘     └────────────────────┘     └─────┬──────┘
                                                           │
                  ┌────────────────────────────────────────┘
                  ▼
     ┌────────────────────────┐    ┌─────────────────────┐    ┌──────────────────┐
     │  Retriever             │───▶│ Generator           │───▶│ FastAPI /chat    │
     │  (top-k cosine,        │    │ (Claude Sonnet 4.6, │    │ (rate-limited,   │
     │   optional rerank      │    │  prompt + cite      │    │  CORS-locked,    │
     │   via bge-reranker)    │    │  parsing)           │    │  demo-key gate)  │
     └────────────────────────┘    └─────────────────────┘    └────────┬─────────┘
                                                                       │
                                                                       ▼
                                                             ┌──────────────────┐
                                                             │ Next.js chat UI  │
                                                             │ (citations,      │
                                                             │  source drawer)  │
                                                             └──────────────────┘
```

## Request path (POST /chat)

1. **Browser** submits a question to `/api/chat` on the Vercel domain.
2. **Vercel server route** (`frontend/app/api/chat/route.ts`) proxies to the FastAPI backend on Fly.io. The `API_URL` and optional `DEMO_KEY` are server-side only — never in the client bundle.
3. **FastAPI** (`backend/app/main.py`) runs the request through:
   - slowapi rate limiter (10 req/min per IP)
   - demo-key check (`x-demo-key` header), if `DEMO_KEY` is set
   - `ChatService.chat()` orchestrator
4. **Retriever** (`backend/app/services/retriever.py`) embeds the query with BGE-small (using the BGE retrieval prefix), pulls top-K from Chroma. If `RERANKER_ENABLED=true`, fetches top-20 instead and rescores with `bge-reranker-base` before returning the top 5.
5. **Generator** (`backend/app/services/generator.py`) builds an XML-tagged prompt with retrieved chunks, calls `claude-sonnet-4-6`, parses inline `[chunk_id]` citations.
6. **ChatService** validates citations against the retrieved set (drops hallucinated IDs), measures per-step latency, returns the structured response.

Median latency at the moment of writing: retrieve 18 ms, generate 1.5–2 s, total ~2 s for a baseline call.

## Deploy topology

- **Backend on Fly.io.** `infra/Dockerfile` builds a multi-stage image (Python 3.11-slim base, uv install, non-root user). The build pre-downloads BGE-small + bge-reranker weights into `HF_HOME` so the running container never calls out to Hugging Face. The Chroma store from `data/chroma/` is **baked into the image** at build time — no Fly volume mount, no remote ingest. To update the corpus: `make ingest` locally, then `make deploy-api`.
- **Frontend on Vercel.** Standard Next.js deploy. Root Directory set to `frontend/` in the Vercel project settings. Server-side env vars: `API_URL` (Fly URL), `DEMO_KEY` (matches Fly secret).
- **Anthropic** is the only runtime third-party dependency. No OpenAI, no hosted embedder, no LangSmith.

## Data lifecycle

```
fairwork.gov.au          one-shot scrape, polite UA + robots.txt + 1 req/s
       │
       ▼
data/raw/*.html          gitignored (regenerable)
       │
       ▼ trafilatura → markdown + YAML frontmatter
data/processed/*.md      committed (corpus lockfile in manifest.json)
       │
       ▼ make ingest (chunk → embed → upsert)
data/chroma/             gitignored locally; baked into Fly image at deploy
```

The `data/processed/` checkin makes the corpus reproducible without re-scraping. Ingestion is deterministic given a fixed chunker config.

## Key design decisions (ADRs)

- [ADR-0001: No LangChain](decisions/0001-no-langchain.md) — direct SDK calls, ~200 LoC of plumbing, debuggable surface area.
- [ADR-0002: Cross-encoder reranking — keep as opt-in flag](decisions/0002-reranking.md) — mixed results, default off, hybrid retrieval likely the better next experiment.
- [ADR-0003: BGE-small (local) over OpenAI embeddings](decisions/0003-bge-over-openai-embeddings.md) — zero per-token cost, one fewer vendor, asymmetric query/doc encoding.
- [ADR-0004: Claude Haiku as judge](decisions/0004-haiku-as-judge.md) — cost + speed; same-family bias acknowledged.

## What's deliberately out of scope

- Authentication or per-document ACLs. Single-tenant read-only demo.
- Streaming responses. Adds complexity to the eval harness for no measurable quality benefit.
- Incremental ingestion. Full rebuild on corpus change. Re-keying on doc-hash is documented as future work in the README.
- Multi-tenant or per-user state. No history persistence beyond the current browser session.
