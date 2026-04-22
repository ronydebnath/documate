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

## 5. Results changelog

Append a row whenever you run an experiment worth remembering. Most recent first.

| Date       | Config          | Hit@5 | MRR  | Faithfulness | Citation Acc. | Notes |
|------------|-----------------|-------|------|--------------|---------------|-------|
| _pending_  | baseline        | –     | –    | –            | –             | To be run after first 30-entry dataset is complete. |

## 6. Known limitations of this eval setup

- ~30 hand-crafted pairs is not a statistically robust benchmark; it's a regression guard plus a directional comparator.
- Judge and generator are both Claude-family models — scores are known to be optimistic vs. a cross-provider judge.
- No inter-rater agreement measurement — there is only one rater (the judge).
- Dataset is static; no coverage of query drift over time.

These are called out deliberately. The goal is to ship measurable improvements on a real dataset, not to claim a benchmark.
