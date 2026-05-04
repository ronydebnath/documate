# DocuMate

An internal knowledge assistant that answers employee questions over company docs, with inline citations. Built end-to-end: ingestion pipeline → vector retrieval → Claude → Next.js chat UI, plus a custom evaluation framework.

**[Live demo](#)** · **[Architecture](docs/architecture.md)** · **[Evals](docs/evals.md)**

![DocuMate empty-state hero with wordmark, headline "Plain answers, with the source.", four suggested questions, and a composer](docs/diagrams/screenshot-empty-state.png)

<sub>An answered conversation: inline `[1]` / `[2]` citation markers, clickable chips below labelled by source title, and a latency breakdown.</sub>

![Answered conversation: assistant explains casual employee leave entitlements with two inline citation markers and chips for "Annual leave" and "National Employment Standards"](docs/diagrams/screenshot-answered.png)

<sub>Clicking a chip opens the right-side source drawer with excerpt, chunk ID, and a link to the original Fair Work Ombudsman page.</sub>

![Source drawer panel showing the National Employment Standards excerpt, chunk ID, and source URL](docs/diagrams/screenshot-source-drawer.png)

## Why

Employees waste hours hunting for answers that already exist in policy docs, runbooks, and onboarding wikis. DocuMate is a thin, focused RAG app that demonstrates a production shape for this problem — not a demo notebook.

Scope: single-tenant, read-only corpus ([Fair Work Australia](https://www.fairwork.gov.au/)), answers with inline citations, and a repeatable eval framework so retrieval/generation changes can be measured.

## Corpus

DocuMate indexes ~40–60 pages from the [Fair Work Ombudsman](https://www.fairwork.gov.au/) website, covering six topic areas of practical employer/employee questions:

1. Pay and wages (minimum wage, penalty rates, allowances)
2. Leave (annual, personal/carer's, parental, long service)
3. Ending employment (notice, redundancy, unfair dismissal)
4. Employment conditions (hours, breaks, rosters)
5. Awards (modern awards overview)
6. Small business

The seed URLs are version-controlled at [backend/scripts/sources.yaml](backend/scripts/sources.yaml). Pages are fetched once via `make scrape`, normalized to markdown with [trafilatura](https://trafilatura.readthedocs.io/), and committed to [data/processed/](data/processed/) along with [data/processed/manifest.json](data/processed/manifest.json) — the corpus lockfile. Re-running the scraper is idempotent. News, media releases, case studies, and PDFs are filtered out.

**Attribution:** Content © Commonwealth of Australia (Fair Work Ombudsman), used under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). DocuMate is an unofficial, non-commercial portfolio project and is not affiliated with or endorsed by Fair Work.

## How it works

> _Architecture diagram placeholder — export from Excalidraw to `docs/diagrams/architecture.png`._

1. **Ingest:** HTML docs → normalized → chunked (recursive, 500 tok / 50 overlap) → embedded locally (`BAAI/bge-small-en-v1.5` via sentence-transformers, runs on CPU) → ChromaDB.
2. **Retrieve:** top-k cosine search; optional cross-encoder reranking (see eval results).
3. **Generate:** Claude Sonnet answers with retrieved context. Prompt enforces *"answer only from context or say you don't know"* and cites chunk IDs.
4. **UI:** Next.js chat. Citations are clickable chips that scroll to the source chunk.

## Quickstart

```bash
# Prereqs: Python 3.11+, Node 20+, uv, pnpm
cp .env.example .env   # fill in ANTHROPIC_API_KEY

make install           # uv sync + pnpm install
make ingest            # loads data/raw/ → data/chroma/
make dev               # FastAPI on :8000, Next.js on :3000
make eval              # runs the baseline eval config
```

## Evaluation

Custom eval framework measuring retrieval quality and answer faithfulness against a hand-crafted dataset of ~30 Q&A pairs across 6 categories (factual lookup, multi-hop, aggregation, negation, out-of-scope, ambiguous).

| Config               | Hit@5 | MRR  | Faithfulness | Citation F1 | MustContain | Refusal |
|----------------------|-------|------|--------------|-------------|-------------|---------|
| Baseline (n=30)      | 0.96  | 0.90 | 0.97         | 0.64        | 0.87        | 0.43    |
| + Cross-enc. rerank  | _TBD_ | _TBD_| _TBD_        | _TBD_       | _TBD_       | _TBD_   |

Per-category breakdown (n shown):

| Category            | n | Hit@5 | MRR  | Faithful | Cite F1 | MustContain | Refusal |
|---------------------|---|-------|------|----------|---------|-------------|---------|
| factual_lookup      |10 | 1.00  | 0.95 | 1.00     | 0.80    | 1.00        | —       |
| multi_hop           | 5 | 1.00  | 0.84 | 0.80     | 0.37    | 0.60        | —       |
| aggregation         | 4 | 1.00  | 1.00 | 1.00     | 0.75    | 1.00        | —       |
| negation            | 4 | 0.75  | 0.75 | 1.00     | 0.50    | 0.75        | —       |
| out_of_scope        | 4 | —     | —    | 1.00     | —       | 0.75        | 0.75    |
| ambiguous           | 3 | —     | —    | 1.00     | —       | 1.00        | 0.00    |

**What the baseline shows.** Retrieval is strong (Hit@5 = 0.96, MRR = 0.90) and faithfulness is high (0.97) — the system rarely fabricates facts that aren't in the retrieved context. The two real weaknesses are **multi-hop synthesis** (Faithful drops to 0.80, MustContain to 0.60: the model retrieves both relevant pages but often declines to combine them, hedging instead of answering) and **clarifying ambiguous queries** (Refusal accuracy = 0/3: when a question is under-specified, the model answers anyway with whatever context retrieves rather than asking which-leave-type / employer-or-employee). The OOS adversarial entry on superannuation rates also failed (model answered "12%" from a corpus chunk that legitimately mentions it) — that's a genuine tension between "answer only from context" and "decline topics outside Fair Work's remit," which a confidence-gated refusal in Phase 6 could address. Citation F1 of 0.64 is dragged down by the model occasionally citing a sister-section page (e.g. `sb-paying-employees` instead of the main `pay-and-wages-paying-wages`) that contains the same fact — fixable by listing all valid source slugs in the dataset.

Methodology, judge prompt, slug-prefix matching, and the full report in [docs/evals.md](docs/evals.md) and [backend/evals/reports/](backend/evals/reports/).

## Engineering decisions

- **No LangChain** — direct SDK calls keep the surface area small and auditable ([ADR-0001](docs/decisions/0001-no-langchain.md)).
- **Chroma over Qdrant/pgvector** — zero-infra file-backed store is right for this scope; swap is ~50 LoC behind the retriever interface.
- **Embedder / generator / retriever as separate services** — each is one function; makes experiments (reranking, hybrid search, query rewriting) a small diff.
- **Judge model ≠ generator model** where possible, to reduce LLM-as-judge bias.

## Limitations

- Single corpus, no per-document ACLs.
- No incremental ingestion — full rebuild on doc changes.
- Evaluated on ~30 hand-crafted pairs; not a statistically robust benchmark.
- No streaming responses in the current UI.

## What I'd do next

- Hybrid retrieval (BM25 + vector) with fusion ranking.
- Query decomposition for multi-hop questions.
- Structured refusal: return `{"answer": null, "reason": "..."}` when retrieval confidence is below threshold.
- Incremental ingestion keyed on doc hash.
- Expand eval set to 150+ pairs and measure inter-rater agreement on a sample.

## Stack

Python · FastAPI · ChromaDB · Anthropic SDK · sentence-transformers (local embeddings) · Next.js · Tailwind · Fly.io · Vercel

## License

MIT — see [LICENSE](LICENSE).
