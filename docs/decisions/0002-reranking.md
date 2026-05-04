# ADR-0002: Cross-encoder reranking, keep or drop?

- **Status:** Accepted
- **Date:** 2026-05-05

## Context

The Phase 5 baseline (n=30, BGE-small embeddings, top-5 retrieval) showed:

- Strong on `factual_lookup` and `aggregation` (Hit@5 = 1.00 in both).
- Citation F1 dragged down by sister-page citations (e.g. `sb-paying-employees` instead of the canonical pay-and-wages page).
- `multi_hop` MRR = 0.84 — top result not always the most relevant page when the question needs synthesis across two docs.

The standard next move is to add a cross-encoder reranker: fetch top-N (= 20) from BGE, rescore each (query, chunk) pair with `BAAI/bge-reranker-base`, return top-5 by reranker score. This typically helps MRR and Citation F1 on small corpora because the reranker has more signal than cosine on a 384-dim vector.

## Options considered

1. **Cross-encoder rerank (this ADR)** — `BAAI/bge-reranker-base`, top-20 → top-5. Adds ~500 ms per query latency. No new config infra; lives behind `settings.reranker_enabled`.
2. **Hybrid retrieval (BM25 + vector)** — fuse lexical and semantic scores. Helps with rare-term queries (acronyms, names). Larger code change; deferred unless rerank shows it's needed.
3. **Better embeddings (`bge-large-en-v1.5`)** — bigger model, slower, and download is ~1.3 GB. Probably overkill at this corpus size.
4. **Do nothing** — keep BGE-small alone. Acceptable if the baseline is already at ceiling for this corpus.

Picked option 1 because it's the cheapest experiment to run, the eval harness already supports per-config swaps, and the result (positive or null) is informative either way.

## Implementation

- New module: [backend/app/services/reranker.py](../../backend/app/services/reranker.py) — lazy-loaded `CrossEncoder` singleton.
- Retriever change: [backend/app/services/retriever.py](../../backend/app/services/retriever.py) accepts an optional reranker callable; when present, fetches `rerank_candidates` (default 20) from Chroma and passes them through.
- Config additions: `RERANKER_ENABLED`, `RERANK_CANDIDATES`, `RERANKER_MODEL` in [backend/app/config.py](../../backend/app/config.py).
- Eval config: [backend/evals/configs/reranked.yaml](../../backend/evals/configs/reranked.yaml).
- Run with diff: `make eval-rerank` calls `run_eval.py --config reranked --compare-to baseline`. The reranked report's markdown gets a `## Comparison vs baseline` section appended automatically.
- Reranker latency stays inside `retrieve_ms` so the slowdown is visible in latency tables, not hidden.

## Result snapshot

Numbers below are the verbatim output of the comparison block in the latest reranked report ([backend/evals/reports/](../../backend/evals/reports/)). Run: `n=30`, baseline 2026-05-02, reranked 2026-05-04.

| Slice           | Hit@5         | MRR              | Faithful         | Cite F1         | MustContain     | Refusal       |
|-----------------|---------------|------------------|------------------|-----------------|-----------------|---------------|
| **all**         | 0.96 → 0.96   | 0.90 → 0.84 ▼    | 0.97 → 0.93 ▼    | 0.64 → 0.78 ▲   | 0.87 → 0.90 ▲   | 0.43 → 0.43   |
| factual_lookup  | 1.00 → 1.00   | 0.95 → 0.95      | 1.00 → 1.00      | 0.80 → 0.83 ▲   | 1.00 → 1.00     | —             |
| multi_hop       | 1.00 → 0.80 ▼ | 0.84 → 0.60 ▼    | 0.80 → 0.80      | 0.37 → 0.50 ▲   | 0.60 → 0.80 ▲   | —             |
| aggregation     | 1.00 → 1.00   | 1.00 → 0.88 ▼    | 1.00 → 1.00      | 0.75 → 0.83 ▲   | 1.00 → 1.00     | —             |
| negation        | 0.75 → 1.00 ▲ | 0.75 → 0.83 ▲    | 1.00 → 1.00      | 0.50 → 0.92 ▲   | 0.75 → 0.75     | —             |
| out_of_scope    | —             | —                | 1.00 → 1.00      | —               | 0.75 → 0.75     | 0.75 → 0.75   |
| ambiguous       | —             | —                | 1.00 → 0.67 ▼    | —               | 1.00 → 1.00     | 0.00 → 0.00   |

Reranker latency added: median retrieve **18 ms → ~2000 ms** (cross-encoder runs on CPU and rescores 20 candidates per query). Cold-start penalty on first query of the run is ~7 minutes for model download; subsequent queries hit the cached weights.

Regressions surfaced by the harness:
- `overall` · MRR: −0.06
- `overall` · Faithful: −0.03
- `aggregation` · MRR: −0.12
- `ambiguous` · Faithful: −0.33 (n=3, single-case sensitivity)
- `multi_hop` · Hit@k: −0.20
- `multi_hop` · MRR: −0.24

Largest improvements:
- `negation` · Cite F1: +0.42
- `negation` · Hit@k: +0.25
- `multi_hop` · MustContain: +0.20
- `overall` · Cite F1: +0.13
- `multi_hop` · Cite F1: +0.13

## Decision

**Keep rerank as an opt-in flag (`RERANKER_ENABLED`, default off).**

The result is genuinely mixed and the latency cost is severe. The single best argument for adoption is Citation F1 (+0.13 overall, +0.42 on `negation`), which is the metric that most directly tracks "did the model cite the right page." That is a real gain. But:

- **MRR regressed 0.06 overall and 0.24 on `multi_hop`.** Cross-encoder `(query, chunk)` similarity is sometimes *less* informative than vector cosine when the answer needs synthesis across two pages. Reordering by surface similarity actively hurts the multi-hop slice.
- **Hit@5 dropped 0.20 on `multi_hop`.** Reranking can push a gold chunk *out* of the top-5 if a sister page scores higher on lexical overlap. That is the worst kind of regression: the right context was retrieved, then discarded.
- **Latency went from 18 ms to ~2000 ms.** That is the single change that makes the median user experience worse, and it is not amortizable, every query pays it.
- **Faithful −0.33 on `ambiguous` is n=3 noise**, not a real signal, but it should not be averaged into a win either.
- **The Cite F1 lift is partly an eval-set artefact.** The baseline citation failure was largely sister-page slugs (`sb-paying-employees` vs `pay-and-wages-paying-wages`). Expanding `expected_source_ids` in the dataset would close most of that gap without any retrieval change, see [What I'd try next](#what-id-try-next).

Default-off is the honest call: the experiment ran, the eval surfaced the regressions the harness was designed to catch, and the cost/benefit does not justify forcing every user to wait two seconds per query for a citation lift that the dataset itself can partially explain.

## Consequences

**Cost of keeping the flag:**
- One extra config knob (`RERANKER_ENABLED`) and a lazy-loaded `CrossEncoder` singleton in [backend/app/services/reranker.py](../../backend/app/services/reranker.py). ~50 LoC, no new infra.
- ~440 MB on disk for `BAAI/bge-reranker-base` weights, only downloaded when the flag is on.
- The eval harness now supports `--compare-to`, which is generally useful and stays regardless of this decision.

**What the flag buys when turned on:**
- Citation F1 +0.13 overall, +0.42 on `negation`, +0.13 on `multi_hop`, +0.08 on `aggregation`.
- MustContain pass rate +0.20 on `multi_hop` (the reranked context unblocks synthesis the baseline hedged on).
- Hit@5 +0.25 on `negation`.

**What it costs when turned on:**
- Median retrieve latency 18 ms → ~2000 ms (cross-encoder rescores 20 candidates on CPU per query).
- Cold-start ~7 minutes on first query (model download).
- MRR −0.06 overall, −0.24 on `multi_hop`. Hit@5 −0.20 on `multi_hop`.

**Categories unaffected:** `factual_lookup` is essentially flat across every metric, and `out_of_scope` refusal is unchanged. Both match expectations: factual lookups already retrieve the correct chunk in rank 1, and refusal is driven by the system prompt, not retrieval order.

**Followups:** the `multi_hop` regression is the strongest signal that hybrid retrieval (BM25 + vector with RRF fusion) is the right next experiment, not a bigger reranker. Tracked under [What I'd try next](#what-id-try-next).

## What I'd try next

- **Hybrid retrieval (BM25 + vector with RRF fusion)** if reranking didn't help on `multi_hop` — lexical signal often unblocks queries the vector retriever misses on rare terms.
- **Per-source-id eval expansion** — add the sister-page slugs to `expected_source_ids` in dataset.yaml (e.g. `sb-paying-employees` alongside `pay-and-wages-paying-wages`). The current Citation F1 of 0.64 is partly an eval-set artefact.
- **Confidence-gated refusal** if `oos-004` (superannuation rate) keeps slipping through — short-circuit to the refusal phrase when max retrieval distance exceeds a threshold OR when retrieved chunks fail a topic classifier.
- **Prompt update for ambiguous queries** — current refusal accuracy on `ambiguous` is 0/3. The system prompt doesn't currently encourage clarifying questions; adding "If the question is under-specified, ask which {leave type / employment type / scenario} the user means" should move the needle.

## Revisit trigger

Revisit this decision when:

- The corpus grows past ~200 pages (more retrieval candidates → reranker has more headroom).
- A new BGE reranker variant (e.g. `bge-reranker-v3`) shows >2pp MRR over `bge-reranker-base` on benchmark sets.
- A user-reported answer-quality regression points at retrieval ranking specifically.
