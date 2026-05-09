# ADR-0003: BGE-small (local) over OpenAI embeddings

- **Status:** Accepted
- **Date:** 2026-04-23

## Context

DocuMate needs an embedder for both ingestion (one-shot, ~145 chunks) and query time (every `/chat` request). The default 2026 choice for a portfolio RAG is `text-embedding-3-small` from OpenAI: 1536-dim, $0.02 per 1M tokens, hosted, fast.

The alternative is a local model via `sentence-transformers`. The BAAI BGE family is the strongest open option in the small-model class on the MTEB leaderboard; `bge-small-en-v1.5` is 384-dim, ~130 MB on disk, runs comfortably on CPU.

A portfolio project gets to make this trade-off in either direction; the cost is whichever set of consequences you're willing to own.

## Options considered

1. **`text-embedding-3-small` (OpenAI).** Hosted. Larger vectors (1536-d). Negligible per-query cost. Adds a second vendor dependency and a second API key.
2. **`text-embedding-3-large` (OpenAI).** 3072-d. Stronger but ~3x the cost; overkill for a 60-page corpus.
3. **`BAAI/bge-small-en-v1.5` (local, this ADR).** 384-d, CPU-friendly, no API key, asymmetric query/document encoding (BGE's defining feature).
4. **`BAAI/bge-large-en-v1.5` (local, larger).** 1024-d, ~1.3 GB download, materially slower on CPU. Probably overkill for this corpus size.

## Decision

Use `BAAI/bge-small-en-v1.5` via `sentence-transformers`. Single implementation in [backend/app/services/embedder.py](../../backend/app/services/embedder.py); imported by both the ingest CLI and the FastAPI app so document and query encoding can never drift.

The asymmetric encoding is the part that matters in code: `embed_documents()` encodes raw text, `embed_query()` prepends `"Represent this sentence for searching relevant passages: "` per the BGE model card. A naive `embed()` API would silently use the wrong encoding for queries and cosine scores would degrade by 5–10% with no error to surface the problem.

## Consequences

### Positive

- **Zero per-token cost on the embedder side.** Anthropic still charges for generation and judging; the embedder is free at every scale this project will ever hit.
- **One fewer vendor.** No OpenAI account, no second API key in the env, no second status page to watch. Reduces the "what's broken today" surface area to Anthropic + Fly + Vercel.
- **Hugging Face cache is portable.** The Dockerfile pre-downloads weights into `HF_HOME` at build time and the runtime sets `HF_HUB_OFFLINE=1`, so the deployed container never phones home. Self-contained image; no surprise outages from hf.co.
- **Smaller vectors → less Chroma memory.** 384-d vs 1536-d is 4x smaller per chunk, which matters more at corpus sizes than at this one but it's free upside.
- **CPU-only is fine at this corpus size.** Median embed latency on Fly's `shared-cpu-2x` is ~30 ms per query (BGE-small is small enough to amortise on CPU).

### Negative

- **First-run model download on dev machines is ~130 MB.** Annoying once, mitigated by the HF cache afterwards.
- **Cold-start on Fly takes ~6 s** while sentence-transformers loads weights from the baked HF cache into memory. We surface this in the latency table and the README rather than hide it.
- **MTEB scores on `bge-small` lag `text-embedding-3-large` by 2–4 pp.** For 60 pages of homogeneous content (Fair Work HTML), this gap is invisible — Hit@5 is already 0.96 on the baseline. At 1000+ docs with diverse domains, the gap may matter and this decision should be revisited.
- **No usage analytics.** Hosted APIs give you a dashboard. Local has none. Doesn't matter at this scale.

### When to revisit

- The corpus grows past ~1000 documents and Hit@5 starts to slip. Try `bge-large` first (still local), then a hosted model as the final escalation.
- A new BGE variant (e.g. `bge-en-v2`) shows >3 pp on benchmark sets that resemble this corpus.
- Cold-start time on Fly becomes a user-visible problem (e.g. multiple users complaining). At that point, switch to a hosted embedder so the container doesn't need to load weights at boot.
