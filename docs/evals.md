# Evaluation methodology

## Why this document exists

The whole point of having evals is simple: **before you change anything, run the eval. After, run it again. Quote the delta.** Without that loop, tuning RAG systems is vibes-coding.

This document is the permanent record of *how* DocuMate is evaluated — the dataset shape, metrics, judge design, and the changelog of results across experiments.

## 1. Dataset

Location: [`backend/evals/dataset.yaml`](../backend/evals/dataset.yaml).

The dataset is ~30 hand-crafted question/answer pairs written against the Fair Work Australia corpus. Each entry follows this schema:

```yaml
- id: fw-notice-001
  category: factual_lookup
  difficulty: easy
  question: "What is the minimum notice period when resigning in Australia?"
  reference_answer: >
    1-3 sentence paraphrase of the correct answer. Not a doc copy-paste.
  expected_source_ids:
    - fairwork/notice-of-termination-and-redundancy-pay
  must_contain:
    - "1 week"
    - "4 weeks"
  must_not_contain: []
  notes: "Why this item exists / which failure mode it guards against."
```

### Field reference

| Field                | Drives                                                      |
|----------------------|-------------------------------------------------------------|
| `expected_source_ids`| Retrieval metrics (precision@k, recall@k, MRR, hit@k)       |
| `must_contain`       | Deterministic content check — cheap regression guard        |
| `must_not_contain`   | Catches hallucination / contamination                       |
| `reference_answer`   | Input to LLM-as-judge for relevance and faithfulness        |
| `category`/`difficulty`| Enables slicing (e.g. "reranking helps on multi-hop but hurts on factual") |

### Category coverage (target ~5 entries each)

| Category         | Tests                                    |
|------------------|------------------------------------------|
| `factual_lookup` | Single-chunk direct answer               |
| `multi_hop`      | Combining 2+ chunks                      |
| `aggregation`    | List / count questions                   |
| `negation`       | Answer is "no" / "not required"          |
| `out_of_scope`   | Must refuse gracefully                   |
| `ambiguous`      | Paraphrased / under-specified queries    |

The `out_of_scope` category is the sneakiest differentiator — most portfolio RAGs happily hallucinate on these. Grading refusal is a production concern, not a nicety.

### Building and growing the dataset

1. Read 10–15 real doc pages yourself before writing any questions — so the questions sound like what a real employee would ask.
2. Fill `expected_source_ids` *as you write* — if you don't know which doc the answer lives in, the entry is weak.
3. Paraphrase for `reference_answer`; never copy-paste from the corpus.
4. Sanity-check a random 5 entries 24 hours later. If you can't answer your own question from your own reference, the entry is broken.

Budget: ~3–4 hours for 30 entries.

## 2. Metrics

### Retrieval metrics — *is the right context even being fetched?*

| Metric        | What it measures                                                  | Why it matters |
|---------------|-------------------------------------------------------------------|----------------|
| `hit@k`       | Binary: did *any* expected source appear in top-k?                | Floor metric. If hit@5 is low, no prompt tuning will save you. |
| `precision@k` | Of the top-k retrieved, fraction that are relevant                | Noise indicator — low precision distracts the generator. |
| `recall@k`    | Of expected sources, fraction appearing in top-k                  | Coverage for multi-hop questions. |
| `MRR`         | Mean reciprocal rank of the first relevant chunk                  | Sensitive to rank order; improves most with reranking. |

### Generation metrics — *is the actual output good?*

| Metric               | Method                   | What it measures |
|----------------------|--------------------------|------------------|
| `must_contain_pass`  | String match             | Cheap regression guard. |
| `faithfulness`       | LLM judge, 0–1           | Every claim in the answer is supported by retrieved context. (Anti-hallucination.) |
| `relevance`          | LLM judge, 0–1           | Answer actually addresses the question. |
| `citation_accuracy`  | LLM judge, 0–1           | Each citation in the answer actually supports the claim it annotates. |
| `refusal_correct`    | Binary, out_of_scope only| System correctly declines for out-of-scope questions. |

## 3. LLM-as-judge design

### Principles

- **Structured output** via tool use — non-negotiable for reproducibility.
- **One judgment per call.** Asking one prompt to score faithfulness *and* relevance *and* citations causes calibration drift. Make N calls.
- **Rubric in the prompt.** Not "score 0–1" but a table tying each score to an observable condition.
- **Reasoning before the score.** Chain-of-thought before the final number measurably improves calibration.
- **Judge ≠ generator** where the budget allows. Default: `claude-sonnet-4-6` generates; `claude-haiku-4-5` judges. Note in the results if they share a family (they do here) — this is a known bias and we call it out rather than hide it.

### Faithfulness rubric (example)

```
1.0  — Every factual claim in the answer is directly supported by the context.
0.75 — All core claims supported; minor embellishment not present in context.
0.5  — Most claims supported, but one material claim is unsupported.
0.25 — Answer relies substantially on information not in the context.
0.0  — Core answer is fabricated or contradicts the context.

Before scoring, list each claim and mark it SUPPORTED, PARTIAL, or UNSUPPORTED.
```

## 4. Run and report

Each run is parameterized by a config file in `backend/evals/configs/`:

```bash
uv run python -m evals.run_eval --config baseline
uv run python -m evals.run_eval --config reranked --compare-to baseline
```

Each run writes two artifacts to `backend/evals/reports/` (gitignored):

- `YYYY-MM-DD_<config>.json` — raw per-question results
- `YYYY-MM-DD_<config>.md` — human-readable summary with:
  - Headline metrics table
  - Per-category breakdown
  - Bottom-5 failures by faithfulness (qualitative review)
  - Diff vs. `--compare-to` run, if provided

## 5. Results

All numbers below come from the verbatim outputs of the eval harness in [backend/evals/reports/](../backend/evals/reports/). `n=30` cases across 6 categories.

### 5.1 Headline

| Config                      | Hit@5 | MRR  | Faithfulness | Citation F1 | MustContain | Refusal |
|-----------------------------|-------|------|--------------|-------------|-------------|---------|
| Baseline (BGE-small, top-5) | 0.96  | 0.90 | 0.97         | 0.64        | 0.87        | 0.43    |
| + Cross-encoder rerank      | 0.96  | 0.84 | 0.93         | 0.78        | 0.90        | 0.43    |
| Δ                           | +0.00 | -0.06 ▼ | -0.03 ▼   | +0.13 ▲     | +0.03 ▲     | +0.00   |

Latency: median retrieve **18 ms → ~2000 ms** with rerank (cross-encoder runs on CPU; fetches top-20 from BGE then rescores).

### 5.2 Per-category breakdown (baseline → reranked)

| Category         | n | Hit@5         | MRR            | Faithful       | Cite F1        | MustContain    | Refusal       |
|------------------|---|---------------|----------------|----------------|----------------|----------------|---------------|
| `factual_lookup` |10 | 1.00 → 1.00   | 0.95 → 0.95    | 1.00 → 1.00    | 0.80 → 0.83 ▲  | 1.00 → 1.00    | —             |
| `multi_hop`      | 5 | 1.00 → 0.80 ▼ | 0.84 → 0.60 ▼  | 0.80 → 0.80    | 0.37 → 0.50 ▲  | 0.60 → 0.80 ▲  | —             |
| `aggregation`    | 4 | 1.00 → 1.00   | 1.00 → 0.88 ▼  | 1.00 → 1.00    | 0.75 → 0.83 ▲  | 1.00 → 1.00    | —             |
| `negation`       | 4 | 0.75 → 1.00 ▲ | 0.75 → 0.83 ▲  | 1.00 → 1.00    | 0.50 → 0.92 ▲  | 0.75 → 0.75    | —             |
| `out_of_scope`   | 4 | —             | —              | 1.00 → 1.00    | —              | 0.75 → 0.75    | 0.75 → 0.75   |
| `ambiguous`      | 3 | —             | —              | 1.00 → 0.67 ▼  | —              | 1.00 → 1.00    | 0.00 → 0.00   |

### 5.3 Results changelog

Append a row whenever you run an experiment worth remembering. Most recent first.

| Date       | Config    | Hit@5 | MRR  | Faithful | Cite F1 | Notes                                                          |
|------------|-----------|-------|------|----------|---------|----------------------------------------------------------------|
| 2026-05-04 | reranked  | 0.96  | 0.84 | 0.93     | 0.78    | Cross-encoder `bge-reranker-base`, top-20 → top-5. ADR-0002.   |
| 2026-05-02 | baseline  | 0.96  | 0.90 | 0.97     | 0.64    | First full 30-case run after dataset reached 30 entries.       |

## 6. Observations

Five things worth saying out loud about the numbers above. The honest ones come first.

1. **The baseline is already strong on retrieval.** Hit@5 = 0.96 on 30 cases is close to ceiling for a 60-page corpus with a small embedder. That ceiling explains why reranking has so little room to help on Hit@5 — the right chunk is already in the top-5 most of the time. The reranker can only reorder, not improve a retrieval that's already comprehensive.

2. **Citation F1 = 0.64 baseline is partly an artefact of the dataset, not the retriever.** Several `expected_source_ids` entries name the canonical Fair Work page (e.g. `pay-and-wages-paying-wages`) when sister pages on the small-business sub-site (`sb-paying-employees`) cover the same topic. The retriever is finding *correct* content; the gold set is too narrow to credit it. Tracked under ["What we'd do next"](#7-what-wed-do-next).

3. **Multi-hop is the weakest slice and reranking made it worse.** Baseline `multi_hop`: Hit@5 1.00, MRR 0.84, MustContain 0.60 — high recall, low ranking quality, and the model hedges on synthesis. Reranking improved MustContain (+0.20) but hurt Hit@5 (-0.20) and MRR (-0.24): cross-encoder `(query, chunk)` similarity reorders chunks toward surface lexical match, which on multi-hop questions can push a relevant-but-paraphrased gold chunk *out* of the top-5. This is the strongest signal that hybrid retrieval (BM25 + vector + RRF fusion) is the right next experiment.

4. **The `ambiguous` slice has Refusal = 0/3 in both configs.** The system prompt encourages answering or declining, but doesn't explicitly tell the model to ask a clarifying question when a query is under-specified. This is a prompt issue, not a retrieval one, and is the cheapest meaningful improvement available — a single sentence in the system prompt should move this slice substantially.

5. **`oos-004` ("current superannuation guarantee rate") slipped through refusal.** The corpus actually contains a chunk that mentions "12% of ordinary time earnings", which is true at the time of writing but is exactly the kind of fact that goes stale. Confidence-gated refusal — short-circuit to the refusal phrase when retrieval distance exceeds a threshold OR when the topic classifier disagrees with the question — is the production fix.

## 7. What we'd do next

In rough order of expected lift per hour of work:

- **Expand `expected_source_ids`** with sister-page slugs. The current Citation F1 of 0.64 is a known dataset issue; this closes most of the gap without any code change.
- **System prompt update for ambiguous queries.** Add an instruction to ask which `{leave type, employment type, scenario}` the user means when the question is under-specified. Should move `ambiguous` Refusal from 0/3 toward 2-3/3.
- **Hybrid retrieval (BM25 + vector with RRF fusion).** Direct response to the multi-hop regression observed under reranking. Lexical signal often unblocks queries the vector retriever misses on rare terms (acronyms, specific dollar amounts, statutory references).
- **Confidence-gated refusal.** Threshold on max retrieval distance, or a topic classifier on retrieved chunks. Targets the `oos-004` failure pattern.
- **Cross-provider judge pass.** Run the same eval set with a non-Claude judge (e.g. GPT-4o-mini) on the flagship config. Compare distributions; if Haiku is materially more lenient on the same items, recalibrate the rubric. Tracked in [ADR-0004](decisions/0004-haiku-as-judge.md).

## 8. Known limitations of this eval setup

- **n=30 is a regression guard, not a benchmark.** Slice sizes (`ambiguous` n=3, `negation` n=4) mean a single case flip can move the per-category score by 25-33pp. Treat per-slice deltas under that size with appropriate scepticism.
- **Same-family judging.** Judge and generator are both Claude. Faithfulness scores are likely optimistic vs a cross-provider judge by ~5-10pp (typical literature range). Documented in [ADR-0004](decisions/0004-haiku-as-judge.md). The relative deltas between configs are the load-bearing numbers.
- **No inter-rater agreement.** One judge means Cohen's kappa isn't measurable. Mitigation: the bottom-N failures are always rendered into the markdown report with the judge's reasoning visible for hand-review.
- **Static dataset.** Written once against a frozen scrape of the Fair Work corpus. No coverage of query drift over time, no synthetic adversarial examples.
- **Citation accuracy is approximated by F1 over slugs**, not by checking each citation's specific claim against its specific chunk. The latter would require a per-citation judge call (~30x more spend); deferred until the headline number warrants it.

These are called out deliberately. The goal is to ship measurable improvements on a real dataset, not to claim a benchmark.
