# DocuMate — initial scaffolding plan

## Context

You're building DocuMate, a RAG-based internal knowledge assistant, as a portfolio project for an Atlassian "Employee Productivity and Support" role. The goal isn't a research demo; it's a production-shaped, end-to-end GenAI app that proves you ship full-stack systems with an LLM inside.

This plan covers the three highest-leverage starting artifacts:

1. **Repo structure** — directory skeleton and the rationale for each piece
2. **README skeleton** — the section outline that'll carry the portfolio narrative
3. **Eval set design** — the part most portfolio RAGs skip, and your differentiator

Working directory `/Users/rony/Development/DocuMate` is currently empty. Nothing to preserve or migrate.

## Design decisions baked in (from your brief)

- **Backend:** Python + FastAPI
- **Frontend:** Next.js (App Router, TS)
- **Vector store:** ChromaDB (local, file-backed — no infra)
- **LLM:** Anthropic Claude (Sonnet for generation, optional Haiku for cheap judging). Default to Claude because your CLAUDE.md/ctx7 flow favours it and the API ergonomics are cleaner for citations.
- **Embeddings:** `text-embedding-3-small` (OpenAI) — small, cheap, strong. Keep the embedder behind an interface so you can swap to `sentence-transformers` later if you want to kill the OpenAI dep.
- **No LangChain.** Direct API calls + your own ~200 lines.
- **Package manager:** `uv` for Python (fast, lockfile, modern). `pnpm` for Next.js.
- **Deploy:** Fly.io (backend) + Vercel (frontend).

Flag: if you'd rather start with GPT-4o-mini or use `poetry`/`pip-tools` instead of `uv`, say so before I execute — everything else stays the same.

---

## 1. Repo structure

```
DocuMate/
├── README.md                       # The portfolio narrative
├── LICENSE                         # MIT
├── .gitignore
├── .env.example                    # Documents required env vars
├── Makefile                        # One-liner dev commands (make ingest, make eval, make dev)
│
├── backend/
│   ├── pyproject.toml              # uv-managed
│   ├── uv.lock
│   ├── .python-version
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI entry
│   │   ├── config.py               # Pydantic Settings (env vars)
│   │   ├── schemas.py              # Request/response models
│   │   ├── routes/
│   │   │   ├── chat.py             # POST /chat
│   │   │   └── health.py           # GET /health
│   │   ├── services/
│   │   │   ├── retriever.py        # Vector search + (optional) reranker
│   │   │   ├── generator.py        # Prompt + Claude call + citation stitching
│   │   │   └── embedder.py         # Thin client wrapper (swappable)
│   │   └── prompts/
│   │       └── answer.py           # Answer prompt (string template, versioned)
│   │
│   ├── ingest/
│   │   ├── __main__.py             # `python -m ingest` CLI
│   │   ├── loaders.py              # HTML / PDF / MD → normalized Document
│   │   ├── chunker.py              # Recursive splitter, 500 tokens / 50 overlap
│   │   └── pipeline.py             # load → chunk → embed → upsert Chroma
│   │
│   ├── evals/
│   │   ├── dataset.yaml            # The 20–30 Q&A pairs (see §3)
│   │   ├── run_eval.py             # CLI: python -m evals.run_eval --config baseline
│   │   ├── configs/                # Named configs (baseline, hybrid, reranked)
│   │   │   ├── baseline.yaml
│   │   │   └── reranked.yaml
│   │   ├── metrics/
│   │   │   ├── retrieval.py        # precision@k, recall@k, MRR, hit@k
│   │   │   └── generation.py       # faithfulness, relevance, citation accuracy
│   │   ├── judges/
│   │   │   └── claude_judge.py     # LLM-as-judge w/ structured output
│   │   └── reports/                # gitignored — each run writes a JSON + markdown summary
│   │
│   └── tests/
│       ├── test_chunker.py
│       └── test_retriever.py
│
├── frontend/
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                # Chat UI (one page, no router complexity)
│   │   └── api/chat/route.ts       # Proxies to FastAPI; keeps CORS trivial
│   ├── components/
│   │   ├── ChatInput.tsx
│   │   ├── MessageList.tsx
│   │   ├── Message.tsx
│   │   └── Citations.tsx           # Clickable source chips under each answer
│   ├── lib/
│   │   └── api.ts                  # fetch wrapper
│   └── styles/globals.css
│
├── data/
│   ├── raw/                        # gitignored — source docs (HTML/PDF/MD)
│   ├── processed/                  # gitignored — chunks + manifest.json
│   └── chroma/                     # gitignored — Chroma persist dir
│
├── infra/
│   ├── fly.toml                    # Fly.io config for backend
│   └── Dockerfile                  # Backend image (frontend deploys via Vercel)
│
└── docs/
    ├── architecture.md             # Diagram + key decisions (link from README)
    ├── evals.md                    # Full eval methodology + results changelog
    └── decisions/                  # Lightweight ADRs (why Chroma, why no LangChain, etc.)
        ├── 0001-no-langchain.md
        └── 0002-chunking-strategy.md
```

### Why this shape (the parts worth justifying)

- **`ingest/` as a separate package, not part of `app/`.** Ingestion is batch/offline; the API is online. Keeping them separate means the API image doesn't need loaders or chunking code, and ingestion can run as a one-shot CLI (`python -m ingest`).
- **`services/` with thin, swappable modules.** `retriever.py` / `generator.py` / `embedder.py` each expose one function the API consumes. This is what makes the reranking experiment on Day 6 a 20-line diff instead of a refactor.
- **`evals/configs/` as YAML.** Each eval run is parameterized (top-k, reranker on/off, prompt version) so you can actually do A/B comparisons and reproduce a number you quote in your write-up.
- **`docs/decisions/` (mini-ADRs).** Two or three short ADRs are disproportionately impressive in a portfolio — they're what senior engineers write, and they directly answer "why" questions an interviewer will ask.
- **`Makefile`.** `make ingest`, `make dev`, `make eval`, `make deploy`. One place, no memorization. Reviewers clone and run in 60 seconds.

---

## 2. README skeleton

Structured so a recruiter skimming the top 30 seconds still gets the hook, and an engineer reading in depth finds the eval numbers and tradeoffs.

```markdown
# DocuMate

An internal knowledge assistant that answers employee questions over company docs,
with citations. Built end-to-end: ingestion pipeline → vector retrieval → Claude →
Next.js chat UI, plus a custom evaluation framework.

**[Live demo](https://documate.example.com)** · **[Architecture](docs/architecture.md)** · **[Evals](docs/evals.md)**

![Screenshot or GIF of the chat UI in action]

## Why

Employees waste hours hunting for answers that already exist in policy docs,
runbooks, and onboarding wikis. DocuMate is a thin, focused RAG app that
demonstrates a production shape for this problem — not a demo notebook.

Scope: single-tenant, read-only corpus, answers with inline citations, and
a repeatable eval framework so retrieval/generation changes can be measured.

## How it works

[Architecture diagram — Excalidraw PNG exported to docs/diagrams/]

1. **Ingest:** HTML/PDF/MD docs → normalized → chunked (recursive, 500 tok / 50 overlap)
   → embedded (`text-embedding-3-small`) → ChromaDB.
2. **Retrieve:** top-k cosine search; optional cross-encoder reranking (see eval results).
3. **Generate:** Claude Sonnet answers with retrieved context. Prompt enforces
   "answer only from context or say you don't know" and cites chunk IDs.
4. **UI:** Next.js chat. Citations are clickable chips that scroll to the source chunk.

## Quickstart

\`\`\`bash
# Prereqs: Python 3.11+, Node 20+, uv, pnpm
cp .env.example .env   # fill in ANTHROPIC_API_KEY, OPENAI_API_KEY

make install           # uv sync + pnpm install
make ingest            # loads data/raw/ → data/chroma/
make dev               # runs FastAPI on :8000 and Next.js on :3000
\`\`\`

## Evaluation

Custom eval framework measuring retrieval quality and answer faithfulness
against a hand-crafted dataset of 30 Q&A pairs across 6 categories.

| Config               | Hit@5 | MRR  | Faithfulness | Citation Acc. |
|----------------------|-------|------|--------------|---------------|
| Baseline             | 0.83  | 0.67 | 0.72         | 0.78          |
| + Cross-enc. rerank  | 0.90  | 0.81 | 0.84         | 0.86          |

Full methodology, judge prompt, and per-category breakdown in [docs/evals.md](docs/evals.md).

## Engineering decisions

- **No LangChain** — direct SDK calls keep the surface area small and auditable ([ADR-0001](docs/decisions/0001-no-langchain.md)).
- **Chroma over Qdrant/pgvector** — zero-infra file-backed store is right for this scope; swap is ~50 LoC behind the retriever interface.
- **Embedder/generator/retriever as separate services** — each is one function; makes experiments (reranking, hybrid search, query rewriting) a small diff.
- **Judge model ≠ generator model** where possible, to reduce LLM-as-judge bias.

## Limitations

- Single corpus, no per-document ACLs.
- No incremental ingestion — full rebuild on doc changes.
- Evaluated on 30 hand-crafted pairs; not a statistically robust benchmark.
- No streaming responses in the current UI.

## What I'd do next

- Hybrid retrieval (BM25 + vector) with fusion ranking.
- Query decomposition for multi-hop questions.
- Structured refusal: return `{"answer": null, "reason": "..."}` when confidence < threshold.
- Incremental ingestion keyed on doc hash.
- Expand eval set to 150+ pairs and add inter-rater agreement on a sample.

## Stack

Python · FastAPI · ChromaDB · Anthropic SDK · OpenAI embeddings · Next.js · Tailwind · Fly.io · Vercel
```

### Notes on the skeleton

- **Screenshot/GIF at the top is non-negotiable.** Most portfolio repos bury the demo; reviewers leave before they find it.
- **Eval table front-and-center.** It's the thing that separates you from "followed a YouTube tutorial."
- **"What I'd do next" and "Limitations"** — both signal seniority. Most portfolios try to hide what's missing; owning it reads as mature.

---

## 3. Eval set design — the high-leverage piece

The whole point of having evals is: **before you change anything, you run the eval. After, you run it again. You quote the delta.** Without that, you're just vibes-coding.

### 3.1 Dataset shape

One file, `backend/evals/dataset.yaml`, with 25–30 entries. Each entry:

```yaml
- id: fw-notice-001
  category: factual_lookup
  difficulty: easy
  question: "What's the minimum notice period when resigning in Australia?"
  reference_answer: >
    The minimum notice period depends on years of continuous service:
    1 week if under 1 year, 2 weeks for 1–3 years, 3 weeks for 3–5 years,
    and 4 weeks for over 5 years. Employees over 45 with 2+ years of service
    get an extra week.
  expected_source_ids:
    - fairwork/notice-of-termination-and-redundancy-pay
  must_contain:         # Strings that MUST appear in a correct answer
    - "1 week"
    - "4 weeks"
  must_not_contain: []  # Strings that indicate hallucination
  notes: "Direct lookup; answer is in one chunk."
```

Key fields and why:

- `expected_source_ids` → drives retrieval metrics (precision@k, recall@k, MRR).
- `must_contain` / `must_not_contain` → cheap, deterministic signal on answer content without LLM-as-judge cost. These catch 60% of regressions.
- `category` + `difficulty` → lets you slice results and detect, e.g., "reranking helps on multi-hop but hurts on factual."
- `reference_answer` → the gold string. Used by the LLM judge for relevance/faithfulness scoring.

### 3.2 Category coverage (aim for ~5 per category)

| Category           | What it tests                          | Example |
|--------------------|----------------------------------------|---------|
| `factual_lookup`   | Single-chunk direct answer             | "What's the minimum wage in 2026?" |
| `multi_hop`        | Requires combining 2+ chunks           | "Can I take parental leave and carer's leave in the same year?" |
| `aggregation`      | List/count questions                   | "What types of leave are Australian employees entitled to?" |
| `negation`         | Answer is "no" / "not required"        | "Do casual employees get paid annual leave?" |
| `out_of_scope`     | Must refuse gracefully                 | "What's the weather in Sydney today?" |
| `ambiguous`        | Paraphrases / under-specified          | "How long do I have off after having a baby?" |

The out_of_scope category is the sneakiest differentiator — most portfolio RAGs happily hallucinate on these. Grading refusal behavior shows you thought about the production failure mode.

### 3.3 Metrics (and what each one is actually telling you)

**Retrieval metrics** (answer: is the right context even being fetched?)

| Metric        | What it measures                                          | Why it matters |
|---------------|-----------------------------------------------------------|----------------|
| `hit@k`       | Binary: did *any* expected source appear in top-k?        | Floor metric. If hit@5 is low, no prompt tuning will save you. |
| `precision@k` | Of the top-k retrieved, fraction that are relevant        | Noise indicator. Low precision = generator gets distracted. |
| `recall@k`    | Of expected sources, fraction that appeared in top-k      | Coverage for multi-hop. |
| `MRR`         | Mean reciprocal rank of first relevant chunk              | Sensitive to rank order; improves most with reranking. |

**Generation metrics** (answer: is the actual output good?)

| Metric            | Method                 | What it measures |
|-------------------|------------------------|------------------|
| `must_contain_pass` | String match (deterministic) | Cheap regression guard. |
| `faithfulness`    | LLM judge, 0–1         | Does every claim in the answer appear in the retrieved context? (Anti-hallucination.) |
| `relevance`       | LLM judge, 0–1         | Does the answer actually address the question? |
| `citation_accuracy` | LLM judge, 0–1       | For each citation in the answer, does the cited chunk actually support that claim? |
| `refusal_correct` | Binary, out_of_scope only | For out-of-scope questions, did the system correctly decline? |

### 3.4 Judge prompt — the single highest-leverage prompt

One judge call per metric per question, using Claude Sonnet (generator is also Claude Sonnet — note this limitation in `docs/evals.md`; if budget permits, switch the judge to a different provider for a bias-check pass).

Design principles:

- **Structured output** (JSON schema via tool use) — non-negotiable for reproducibility.
- **One judgment per call.** Don't ask the judge to score faithfulness AND relevance AND citations in one prompt; calibration drifts.
- **Rubric included in the prompt.** Not "score 0–1" but "1 = every claim is supported, 0.5 = one unsupported minor claim, 0 = core claim not in context."
- **Reasoning before score.** Chain-of-thought before the final number improves calibration measurably.

Sketch for the faithfulness judge:

```python
FAITHFULNESS_RUBRIC = """
Score how well the ANSWER is supported by the CONTEXT.

1.0 — Every factual claim in the answer is directly supported by the context.
0.75 — All core claims supported; minor embellishment not present in context.
0.5 — Most claims supported, but one material claim is unsupported.
0.25 — Answer relies substantially on information not in the context.
0.0 — Core answer is fabricated or contradicts the context.

Before scoring, list each claim in the answer and mark it SUPPORTED, PARTIAL, or UNSUPPORTED.
"""
```

### 3.5 Run + report shape

`python -m evals.run_eval --config baseline` produces:

- `backend/evals/reports/2026-04-22_baseline.json` — raw per-question results
- `backend/evals/reports/2026-04-22_baseline.md` — human-readable summary with:
  - Headline table (one row per metric)
  - Per-category breakdown
  - Bottom-5 failures by faithfulness (qualitative)
  - Diff vs. previous run if `--compare-to` is passed

This is what you paste into your LinkedIn post: "Added cross-encoder reranking. Faithfulness +17pp, MRR +21pp. Sample failure modes [x, y]. Code: [link]."

### 3.6 Building the dataset (the part you'll want to skip but shouldn't)

1. Pick the corpus first and ingest it end-to-end with placeholder eval of 3 questions.
2. **Read 10–15 real doc pages yourself.** Don't synthesize questions from thin air — you need to know what a plausible employee question sounds like for that corpus. This is 1–2 hours and it's the difference between a real eval and a toy one.
3. Write questions across the 6 categories, 4–5 each, with `expected_source_ids` filled in *as you write*. You should know which doc contains the answer before you write the question.
4. For `reference_answer`, write 1–3 sentences. Don't copy-paste from the doc — paraphrase, the way the system should respond.
5. Have a friend (or yourself, 24h later) sanity-check 5 random entries. If you can't answer your own question from your own reference, it's a bad entry.

Budget: 3–4 hours for 30 entries. It feels slow because it is — and it's the asset you'll reuse for every experiment.

---

## Verification

Before you start implementing, sanity-check these with me:

1. **Corpus choice.** Fair Work is the strongest default (clean HTML, well-scoped, employee-productivity-framed). Confirm or swap to NDIS/ATO.
2. **Package managers.** `uv` + `pnpm`. Swap if you prefer Poetry/npm.
3. **Ordering.** I'm proposing you scaffold the repo (Day 1), then immediately write 3–5 eval entries (not 30) alongside ingestion so you're never more than a day from a measurable number. Full eval set expansion happens Day 5. Confirm that works for you, or if you'd rather write the full set up front.

Once those three are locked, the scaffolding task is: create the directory tree above, populate `.env.example` / `Makefile` / root `README.md` with the skeletons, and stub `backend/evals/dataset.yaml` with 3 seed entries. ~30–45 minutes of work.

## Critical files to create first (when we exit plan mode)

- `/Users/rony/Development/DocuMate/README.md` (from §2 skeleton)
- `/Users/rony/Development/DocuMate/.gitignore` (Python + Node + `data/` + `.env`)
- `/Users/rony/Development/DocuMate/.env.example`
- `/Users/rony/Development/DocuMate/Makefile`
- `/Users/rony/Development/DocuMate/backend/pyproject.toml`
- `/Users/rony/Development/DocuMate/backend/evals/dataset.yaml` (3 seed entries covering factual_lookup, multi_hop, out_of_scope)
- `/Users/rony/Development/DocuMate/docs/evals.md` (from §3, as the permanent methodology doc)
- `/Users/rony/Development/DocuMate/docs/decisions/0001-no-langchain.md`
