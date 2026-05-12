# DocuMate — Phase-by-Phase Build Plan

A build plan for shipping DocuMate (Fair Work RAG assistant) in ~7–10 working days. Written to be handed to Claude Code in Cursor one phase at a time. 

---

## Patches applied to this version (2026-04-22)

This file has been adjusted from its original Claude-web form to match the actual scaffolded repo:

1. **Directory layout**: Python lives under `backend/` (`backend/app/`, `backend/ingest/`, `backend/evals/`, `backend/tests/`, `backend/scripts/`, `backend/notebooks/`). Frontend lives under `frontend/`. Cursor prompts and DoD paths have been rewritten accordingly.
2. **Model strings**: `claude-sonnet-4-7` → `claude-sonnet-4-6` (the actual latest Sonnet; `4-7` is an Opus identifier and would have failed at runtime).
3. **Eval dataset**: kept as `backend/evals/dataset.yaml` (3 seed entries already written) instead of `data/eval/gold.jsonl`.
4. **ADR-0001**: already exists at `docs/decisions/0001-no-langchain.md`. Phase 8 updated to revise rather than create.
5. **Cover-letter paragraph and CV bullet**: target is **Atlassian** Employee Productivity & Support, not Apple. Verify before submitting.
6. **Ingest module name**: `backend/ingest/` (singular), not `ingestion/`. Matches the scaffolded directory.

---

## How to use this document

1. **One phase at a time.** Don't hand Claude Code the whole plan — it'll hallucinate coupling between phases and make a mess. Paste the phase's "Cursor prompt" block only.
2. **Check the DoD before moving on.** If the Definition of Done isn't met, don't advance. Phase 5 (evals) is where sloppy earlier phases come back to bite you.
3. **Freeze decisions.** Your README already commits to Chroma, BGE embeddings, no LangChain, Claude Sonnet generator, Haiku judge. Don't second-guess these mid-build.
4. **Time estimates are focused work hours.** Double them if you're squeezing this in around a full-time day job.

**Total estimate: 35–50 focused hours across 7–10 elapsed days.**

---

## Global ground rules (paste into Cursor's Rules for AI)

```
You are helping build DocuMate, a Fair Work Australia RAG assistant.

Non-negotiables:
- No LangChain, LlamaIndex, or agent frameworks. Direct SDK calls only.
- Python 3.11+, uv for deps, make for tasks.
- Next.js 14+ App Router, TypeScript, Tailwind, pnpm.
- Embeddings: BAAI/bge-small-en-v1.5 via sentence-transformers (local, CPU).
- Vector store: ChromaDB, file-backed at data/chroma/.
- Generator: claude-sonnet-4-6. Judge: claude-haiku-4-5-20251001.
- Pydantic v2 for all schemas. No dict-shaped APIs.
- Every module has a single responsibility. retriever.py retrieves; it does not generate.
- Tests are pytest, co-located under tests/.
- When I ask for code, output a plan first if the change touches 3+ files. Wait for my go-ahead.
- No emojis in code or logs. No em-dashes in generated docs.
```

---

## Phase 0 — Scaffolding ✓

Already done. README committed, repo structure in place. Don't regenerate it.

---

## Phase 1 — Corpus acquisition (Fair Work Australia)

**Goal:** A frozen corpus of 60–100 pages of Fair Work content in `data/raw/` and `data/processed/`, with a manifest.

**Time:** 3–5 hours

**Why this matters:** The corpus is the project's single biggest quality lever. A noisy scrape means noisy retrieval means embarrassing answers. Spend the time here.

### Target sections (pick 5–6, go deep, don't sprawl)

Aim for topic areas with clear factual Q&A potential:

- Pay and wages (minimum wage, penalty rates, allowances)
- Leave (annual, personal/carer's, parental, long service)
- Ending employment (notice, redundancy, unfair dismissal)
- Employment conditions (hours, breaks, rosters)
- Awards (modern awards overview — avoid individual awards, too much detail)
- Small business (fair work for SMEs)

Skip case law, news, and PDFs for v1. HTML only.

### Tasks

1. Write `backend/scripts/scrape.py` — `requests` + `BeautifulSoup`, polite (1 req/sec, User-Agent identifying the project, respects `robots.txt`).
2. Seed from section index pages; follow internal links one level deep.
3. Extract main content with `trafilatura` (falls back gracefully on messy HTML).
4. Save raw HTML to `data/raw/{slug}.html`, extracted markdown to `data/processed/{slug}.md` with YAML frontmatter (`url`, `title`, `scraped_at`, `section`, `hash`).
5. Write `data/processed/manifest.json` — list of all docs with metadata. This is your corpus lockfile.
6. `.gitignore` already excludes `data/raw/` and `data/chroma/`. Update it to **un-ignore** `data/processed/` so the corpus is reproducible without re-scraping.
7. Add attribution block to README: "Content © Commonwealth of Australia (Fair Work Ombudsman), used under CC BY 4.0."

### Cursor prompt

```
Build the Fair Work scraper for DocuMate.

Create:
- backend/scripts/scrape.py
- backend/scripts/extract.py (HTML -> markdown via trafilatura)
- data/processed/manifest.json (generated)

The repo already has backend/ as the Python root with pyproject.toml, .python-version, and uv lockfile. Add `requests`, `beautifulsoup4`, and `trafilatura` to backend/pyproject.toml dependencies. Run scripts via `uv run python -m scripts.scrape` from inside `backend/`.

Requirements:
- Seed URLs: I will give you 6 section-index URLs from fairwork.gov.au.
- Crawl one level deep from each seed. Stay on fairwork.gov.au.
- Respect robots.txt (use urllib.robotparser).
- Rate limit: 1 request/second, with 2s backoff on 429/503.
- User-Agent: "DocuMate/0.1 (portfolio project; contact: <my email>)".
- Save data/raw/{slug}.html (raw bytes) and data/processed/{slug}.md (trafilatura output + YAML frontmatter).
- Skip pages under 500 chars of extracted text.
- Skip pages whose <title> suggests news, media release, or case study.
- Write data/processed/manifest.json: list of {slug, url, title, scraped_at, section, char_count, sha256}.
- Idempotent: re-running skips URLs already in manifest unless --force.
- Log a summary table at the end: pages per section, total chars, skipped count.

Before writing code, output:
1. The file tree of what you'll create/modify.
2. The rate-limiting approach.
3. The dedup strategy (canonical URLs, tracking params stripped).

Wait for my approval before coding.
```

### Definition of Done

- [ ] `make scrape` (or `cd backend && uv run python -m scripts.scrape`) runs clean
- [ ] `data/processed/` has 40–60 `.md` files (downscoped from 60–100; enough to stress retrieval without ballooning ingest time)
- [ ] `manifest.json` committed under `data/processed/`
- [ ] A README section lists the 5–6 covered topic areas + attribution
- [ ] You've spot-checked 5 random `.md` files for extraction quality
- [ ] **Corpus is frozen.** You will not re-scrape for the rest of the project.

### Gotchas

- Trafilatura's default extraction sometimes drops list items. Check a "leave entitlements" page — if bullets are missing, tune `include_tables=True, include_lists=True`.
- Some Fair Work pages are JS-heavy. If a page comes back empty, don't fight it — drop it and pick another.
- Do not use Playwright/Selenium for this. Overkill, and it'll become the whole project.

---

## Phase 2 — Ingestion pipeline

**Goal:** `make ingest` reads `data/processed/` and populates ChromaDB at `data/chroma/`.

**Time:** 3–4 hours

### Tasks

1. Write a small `Chunker` class in `backend/ingest/chunker.py` — recursive character splitting by headings → paragraphs → sentences, target 500 tokens with 50 overlap. Use `tiktoken` for counting (cl100k_base). About 40–60 lines; no LangChain.
2. Write `backend/app/services/embedder.py` wrapping sentence-transformers' `BAAI/bge-small-en-v1.5`. Normalize embeddings. Batch size 32. Lives under `app/services/` because both ingest (write side) and the API (query side) import from it — single source of truth.
3. Write `backend/ingest/pipeline.py` (entry point: `backend/ingest/__main__.py`):
   - Reads manifest → loads each `.md` → chunks → embeds → upserts to Chroma
   - Metadata per chunk: `doc_slug`, `chunk_id`, `source_url`, `title`, `section`, `char_start`, `char_end`, `token_count`
   - `chunk_id` format: `{doc_slug}::{ordinal}` (stable and debuggable)
4. `backend/scripts/verify_ingest.py` — quick sanity check: collection count, sample 3 chunks, run one test query.

### Cursor prompt

```
Build the ingestion pipeline for DocuMate.

The repo already has `backend/ingest/` and `backend/app/services/` directories scaffolded. Use them. Do NOT create a top-level `ingestion/` module.

Create:
- backend/ingest/__init__.py
- backend/ingest/chunker.py
- backend/ingest/__main__.py (CLI entry; orchestrates load → chunk → embed → upsert)
- backend/ingest/pipeline.py (the orchestrator called from __main__.py)
- backend/ingest/chroma_store.py (thin Chroma client wrapper)
- backend/app/services/embedder.py (shared by ingest and the API; do not duplicate)
- backend/scripts/verify_ingest.py
- backend/tests/test_chunker.py

Chunker requirements:
- Recursive splitter: splits on headings (# ## ###) first, then paragraphs (\n\n), then sentences (. ! ?), then characters.
- Target 500 tokens, overlap 50 tokens, measured via tiktoken cl100k_base.
- Preserves char_start and char_end offsets into the source doc.
- No LangChain. Write it from scratch.
- Test coverage: empty input, single-paragraph input, heading-heavy input, very long paragraph input.

Embedder (backend/app/services/embedder.py):
- sentence-transformers BAAI/bge-small-en-v1.5.
- Normalizes output (cosine-ready).
- Batch size 32, shows a tqdm progress bar.
- Exposes `embed_documents(texts: list[str]) -> list[list[float]]` (no instruction prefix) and `embed_query(text: str) -> list[float]` (BGE retrieval prefix). Document side and query side MUST behave differently — see Gotchas.
- Reads model name and device from `backend/app/config.py` Settings (already scaffolded).

Ingest (run as `cd backend && uv run python -m ingest`):
- Reads data/processed/manifest.json.
- For each doc: load .md, strip frontmatter, chunk, embed, upsert to Chroma collection "fairwork".
- Chroma persistent client at data/chroma/ (path from Settings.CHROMA_PERSIST_DIR).
- Chunk metadata: doc_slug, chunk_id (f"{slug}::{i:04d}"), source_url, title, section, char_start, char_end, token_count.
- --rebuild flag drops and recreates the collection.
- Logs: docs processed, chunks created, total tokens, elapsed time.

Verify script (backend/scripts/verify_ingest.py):
- Prints collection count.
- Runs a test query ("How much notice do I need to give when resigning?") and prints top-3 chunk IDs + titles + first 200 chars.
- Top result MUST come from a notice/termination doc — if it does not, retrieval is broken; check the BGE query prefix first.

Output your plan first.
```

### Definition of Done

- [ ] `make ingest` runs in under 2 minutes on your machine (after the first-run model download of ~120MB)
- [ ] Collection has ~400–1200 chunks (sanity range — scaled to the 40–60 page corpus)
- [ ] `verify_ingest.py` returns sensible top-3 results for a test query
- [ ] Tests pass (`make test`)
- [ ] No duplicate `chunk_id` values

### Gotchas

- BGE embeddings want a query prefix for retrieval: `"Represent this sentence for searching relevant passages: {query}"`. **Queries** get this prefix; **documents** do not. Bake the asymmetry into `embedder.py` itself (`embed_query` adds the prefix; `embed_documents` doesn't) so the retriever can't get it wrong.
- If Chroma errors on re-ingest, you're probably not passing `--rebuild`. Make it the default for now.

---

## Phase 3 — Retrieval + generation

**Goal:** End-to-end "ask → cited answer" working in a notebook, then wired into a FastAPI `/chat` endpoint.

**Time:** 4–6 hours

### Sub-phase 3a — Notebook spike

`backend/notebooks/01_rag_spike.ipynb`:
- Load Chroma collection
- Embed a query (with the BGE prefix)
- Retrieve top-5 chunks
- Build a prompt with XML-tagged context
- Call Claude Sonnet
- Parse answer + citation IDs
- Eyeball 5 questions across categories before writing API code

Why notebook-first: you'll iterate the prompt 10–20 times. Do it in a notebook, not through FastAPI restarts.

### Sub-phase 3b — FastAPI

Endpoints:
- `GET /health` → `{"status": "ok", "collection_size": N}`
- `POST /chat` → request/response below

```
POST /chat
{
  "query": "How much notice do I give when resigning?",
  "history": []
}

200 OK
{
  "answer": "...",
  "citations": [
    {"chunk_id": "notice-periods::0003", "source_url": "...", "title": "...", "snippet": "..."}
  ],
  "retrieved_chunk_ids": ["..."],
  "latency_ms": {"retrieve": 42, "generate": 1850, "total": 1898}
}
```

### Prompt template (XML-tagged, per Anthropic best practice)

```
<role>You are a Fair Work Australia information assistant.</role>

<instructions>
- Answer only from the provided context.
- Cite every claim using [chunk_id] inline after the relevant sentence.
- If the context does not contain the answer, say exactly: "I don't have information on that in the Fair Work documents I have access to."
- Never invent chunk IDs. Never cite chunks not in the context.
- Be concise. Use Australian English.
- Do not give legal advice; direct users to the Fair Work Ombudsman for personal situations.
</instructions>

<context>
{for each chunk}
<chunk id="{chunk_id}" source="{title}">
{chunk_text}
</chunk>
{endfor}
</context>

<question>
{user_query}
</question>
```

### Cursor prompt

```
Implement retrieval and generation for DocuMate.

The repo already has `backend/app/` scaffolded with `routes/`, `services/`, `prompts/` subdirectories. Use them. The embedder already lives at `backend/app/services/embedder.py` from Phase 2 — import from there; do not re-create it.

Create:
- backend/notebooks/01_rag_spike.ipynb (minimal template — load Chroma, query, generate, display)
- backend/app/__init__.py
- backend/app/main.py (FastAPI app, CORS for localhost:3000)
- backend/app/schemas.py (Pydantic v2: ChatRequest, ChatResponse, Citation, LatencyInfo)
- backend/app/services/retriever.py (Retriever class: query_text -> List[RetrievedChunk])
- backend/app/services/generator.py (Generator class: prompt -> AnswerWithCitations)
- backend/app/services/chat_service.py (orchestrates retriever + generator, returns ChatResponse)
- backend/app/routes/chat.py (POST /chat)
- backend/app/routes/health.py (GET /health)
- backend/app/prompts/answer.py (the XML-tagged prompt template; importable string)
- backend/tests/test_generator_parses_citations.py

Retriever:
- Wraps Chroma collection.
- Calls `embedder.embed_query(text)` (which already applies the BGE prefix; do NOT re-prefix here).
- Returns top-k (default 5; from settings.RETRIEVAL_TOP_K) RetrievedChunk objects with chunk_id, text, metadata, distance.

Generator:
- Uses anthropic SDK, model `claude-sonnet-4-6` (from settings.ANTHROPIC_GENERATOR_MODEL).
- Prompt template exactly as specified in the phase doc (XML tags); load from backend/app/prompts/answer.py.
- Parses inline [chunk_id] citations out of the answer text.
- Returns (answer_text, cited_chunk_ids).

ChatService:
- retrieve -> build prompt -> generate -> parse -> resolve citation metadata (match chunk_ids back to retrieved chunks).
- Times each step; includes latency_ms in response.
- If generator cites a chunk_id not in retrieved set, drop it from citations and log a warning.

Endpoints:
- GET /health (collection size, model name)
- POST /chat (ChatRequest -> ChatResponse)

Notebook must work before FastAPI. Show me the notebook output on 5 test questions (mix of factual, multi-hop, out-of-scope) before moving to the API.
```

### Definition of Done

- [ ] Notebook answers 5 test questions sensibly
- [ ] `curl -X POST localhost:8000/chat -d '{"query": "..."}'` returns structured JSON
- [ ] Out-of-scope question returns the refusal string
- [ ] Citation IDs in the answer all exist in `retrieved_chunk_ids`
- [ ] Latency breakdown present

### Gotchas

- Parse citations with a regex, but also validate — LLMs invent IDs. Drop invalid ones silently; log them.
- If answers are too verbose, the issue is almost always the prompt, not the model. Add "Be concise. Max 4 sentences unless the question requires a list."
- Don't stream yet. Streaming adds complexity that buys nothing for evals.

---

## Phase 4 — Frontend + API

**Goal:** A clean, functional chat UI at `localhost:3000`. Not fancy. Functional.

**Time:** 4–5 hours

### Tasks

1. Single page, App Router.
2. Server-side fetch to FastAPI (keeps the API key server-side even in dev — good habit).
3. Message list, auto-scroll to latest.
4. Assistant messages render citations as clickable chips below the answer.
5. Clicking a chip opens a right-side drawer with the chunk's source URL, title, and snippet.
6. Loading state (skeleton or pulsing dot). Error toast on failure.
7. No auth. Session-scoped state, no localStorage.

### Cursor prompt

```
Build the Next.js chat UI for DocuMate.

Stack: Next.js 14 App Router, TypeScript strict, Tailwind, no UI library (no shadcn, no MUI).

The repo already has `frontend/` scaffolded with `app/`, `components/`, `lib/`, `styles/` directories. All paths below are relative to `frontend/`.

Structure:
- frontend/app/page.tsx (chat page, single route)
- frontend/app/api/chat/route.ts (server-side proxy to FastAPI — reads API_URL from env, forwards request)
- frontend/components/MessageList.tsx
- frontend/components/MessageInput.tsx
- frontend/components/CitationChip.tsx
- frontend/components/SourceDrawer.tsx
- frontend/lib/types.ts (mirrors FastAPI schemas in backend/app/schemas.py)
- frontend/lib/api.ts (typed client)

Behaviour:
- On submit: append user message, show skeleton assistant message, call /api/chat, replace skeleton with response.
- Citations render as small pill buttons under the assistant message, labelled with the chunk's doc title (not the raw chunk_id).
- Clicking a chip opens SourceDrawer (right side, ~400px, closable) showing title, source_url (external link), full snippet.
- Errors: show a red inline banner, keep the input enabled.
- No auto-scroll hijacking when the user scrolls up.

Styling:
- Tailwind. Neutral palette (zinc). Max-width 768px content. System font stack.
- No dark mode v1.
- Readable, not styled to death. Looks competent, not designed.

Accessibility:
- Proper semantic HTML (main, article, button).
- Keyboard navigation works (Enter submits, Esc closes drawer).
- aria-live on message list.

Output your component tree and prop interfaces first. Then build.
```

### Definition of Done

- [ ] Ask a question → see an answer with inline `[chunk_id]` references
- [ ] Click a citation chip → drawer shows source
- [ ] Error state reachable (kill the backend and confirm the UI doesn't blow up)
- [ ] Keyboard-only usable
- [ ] Loads in under 1s on localhost

### Gotchas

- Don't render `[chunk_id]` as raw text in the answer. Either replace with a superscript number linking to the chip, or leave the bracket notation — but be consistent.
- If you render Markdown from the answer, sanitize it. `react-markdown` with a link allowlist is fine. Don't use `dangerouslySetInnerHTML`.

---

## Phase 5 — Evals (the differentiator)

**Goal:** Baseline numbers across four metrics, broken out by question category.

**Time:** 6–8 hours. **Do not rush this.** This is the phase that makes your portfolio credible.

### Sub-phase 5a — Dataset construction

`backend/evals/dataset.yaml` — 30 entries. **Hand-write these.** Do not generate them with an LLM. The whole point is that these are ground truth you verified against the actual corpus. **Three seed entries are already in the file** (Phase 0 work); expand to the full 30 across the distribution below.

Distribution:

| Category | Count | What it tests |
|---|---|---|
| Factual lookup | 10 | Single-chunk answer ("What's the minimum notice for 3 years' service?") |
| Multi-hop | 5 | Requires synthesizing 2+ chunks ("How does notice interact with redundancy pay?") |
| Aggregation | 4 | Summarizing across chunks ("List all types of leave available") |
| Negation | 4 | What's NOT covered ("Does Fair Work cover independent contractors?") |
| Out-of-scope | 4 | Should refuse ("What's the GST rate?", "What's the weather?") |
| Ambiguous | 3 | Should ask for clarification ("Can I take leave?") |

Each entry follows the schema already in `dataset.yaml`:

```yaml
- id: fw-notice-001
  category: factual_lookup
  difficulty: easy
  question: "What is the minimum notice period when resigning in Australia?"
  reference_answer: >
    The minimum notice period depends on continuous service: 1 week if under 1 year,
    2 weeks for 1-3 years, 3 weeks for 3-5 years, 4 weeks for over 5 years.
  expected_source_ids:
    - fairwork/notice-of-termination-and-redundancy-pay
  must_contain: ["1 week", "4 weeks"]
  must_not_contain: []
  notes: "Direct lookup; answer is in one chunk."
```

Behavior is **implicit from category**:
- `out_of_scope` → system must refuse
- `ambiguous` → system must ask a clarifying question
- all others → system must answer with citations

`expected_source_ids` are **doc-level slugs** (e.g. `fairwork/notice-and-final-pay`), not chunk-level IDs. The eval harness matches via prefix: a retrieved `chunk_id` like `notice-and-final-pay::0003` counts as a hit if its slug appears in `expected_source_ids`. This keeps the dataset stable across chunker parameter tweaks — you don't have to rewrite the gold set when you change chunk size.

`must_contain` / `must_not_contain` are deterministic content guards: cheap regex/substring checks that catch ~60% of regressions without needing the LLM judge.

### Sub-phase 5b — Eval harness

`backend/evals/run_eval.py`:
- Loads `backend/evals/dataset.yaml`
- For each question: runs the same retrieval + generation pipeline as `/chat` (import `ChatService` from `backend/app/services/chat_service.py`, don't hit the HTTP endpoint)
- Computes four metrics

### Metrics

**Hit@5** (retrieval):
```
hit@5 = 1 if any retrieved chunk's slug is in expected_source_ids else 0
```
A retrieved `chunk_id` of `notice-and-final-pay::0003` matches `expected_source_ids: [fairwork/notice-and-final-pay]` via slug-prefix comparison (strip the `fairwork/` namespace if present). Skipped for `out_of_scope`/`ambiguous` (empty `expected_source_ids`).

**MRR** (retrieval):
```
MRR = 1 / rank_of_first_chunk_whose_slug_is_in_expected_source_ids
    = 0 if no such chunk in top-k
```

**Faithfulness** (generation, LLM-as-judge with Haiku):
- Judge sees: answer + retrieved context
- Judge asks: "Is every factual claim in this answer supported by the retrieved context? Return 0 or 1 and a one-line reason."
- Use Haiku (cheap, different model family for bias reduction). Temperature 0.

**Citation accuracy** (generation):
- For questions where the system is expected to answer (i.e. category ≠ `out_of_scope`/`ambiguous`):
  - precision: cited chunk slugs ⊂ `expected_source_ids` (strict) or retrieved_top5 slugs (lenient)
  - recall: each entry in `expected_source_ids` appears in cited chunk slugs
- Report F1.

**Must-contain pass rate** (generation, deterministic):
- For each entry: every string in `must_contain` appears in the answer; no string in `must_not_contain` appears.
- Report as a pass/fail per entry, then aggregate to a rate.

**Refusal accuracy** (behavioral, for `out_of_scope` and `ambiguous`):
- Binary: did the model refuse / clarify as expected?
- Simple string matching on the refusal phrase + a Haiku check for clarification questions.

### Judge prompt

```
<role>You are evaluating whether an AI answer is grounded in provided source material.</role>

<source_material>
{retrieved_chunks}
</source_material>

<question>{question}</question>

<answer>{answer}</answer>

<task>
For every factual claim in the answer, check whether it is supported by the source material.
A claim is "supported" if the source material contains the information, even if worded differently.
A claim is "unsupported" if it adds information not present in the source material, including plausible-but-ungrounded details.

Return JSON:
{
  "faithful": 0 or 1,
  "unsupported_claims": ["claim 1", "claim 2"],
  "reason": "one-line summary"
}

faithful = 1 only if unsupported_claims is empty.
</task>
```

### Cursor prompt

```
Build the DocuMate eval harness.

The repo already has `backend/evals/` scaffolded with `configs/`, `metrics/`, `judges/`, `reports/` subdirectories, plus `dataset.yaml` containing 3 seed entries. Use them; do not relocate.

Create:
- backend/evals/__init__.py
- backend/evals/schemas.py (EvalCase, EvalResult — Pydantic v2)
- backend/evals/metrics/retrieval.py (hit_at_k, mrr — slug-prefix matching)
- backend/evals/metrics/generation.py (citation_f1, must_contain_pass, refusal_check)
- backend/evals/judges/claude_judge.py (Haiku-based judge, temperature 0, JSON-mode output, strict parsing)
- backend/evals/configs/baseline.yaml (top_k=5, rerank_enabled=false)
- backend/evals/run_eval.py (CLI, loads dataset.yaml, runs pipeline, writes reports/{config}_{timestamp}.json + .md)
- backend/tests/test_metrics.py

Run_eval behaviour:
- --config baseline | reranked (phase 6) — loads matching YAML from backend/evals/configs/
- --subset factual_lookup,multi_hop (optional) — runs only specified categories
- Imports ChatService directly from backend/app/services/chat_service.py. Does NOT hit HTTP.
- Writes backend/evals/reports/{config}_{timestamp}.json with per-case results + aggregates
- Writes backend/evals/reports/{config}_{timestamp}.md with:
  - Overall metrics table
  - Per-category metrics table
  - 5 worst-performing cases with actual vs expected

Metrics:
- Hit@5: any retrieved chunk's slug ∈ entry.expected_source_ids (strip "fairwork/" namespace)
- MRR: reciprocal rank of first such chunk (0 if absent)
- Faithfulness: Haiku judge (claude-haiku-4-5-20251001), JSON output, 0/1
- Citation F1: cited chunk slugs vs entry.expected_source_ids (precision + recall + F1)
- Must-contain pass: every string in entry.must_contain appears in answer; none in entry.must_not_contain do
- Refusal accuracy: for out_of_scope and ambiguous categories — string match on refusal phrase OR Haiku check for clarification question

Skip Hit@5/MRR for out_of_scope and ambiguous (empty expected_source_ids).

Tests must cover:
- hit@5 with partial overlap
- MRR with gold in position 3 -> 1/3
- slug-prefix matching: chunk_id "notice-and-final-pay::0003" matches expected_source_ids ["fairwork/notice-and-final-pay"]
- faithfulness judge parse failure -> returns 0 with an error field
- citation F1 with no cited IDs
- must_contain_pass with one missing required substring -> fail

Output the eval schema and metric formulas first. Wait for approval before coding.
```

### Definition of Done

- [ ] `backend/evals/dataset.yaml` has 30 hand-written entries (started from the 3 seed entries)
- [ ] `make eval` runs end-to-end in under 10 minutes
- [ ] `backend/evals/reports/baseline_*.md` exists with real numbers
- [ ] README baseline row filled in
- [ ] You can articulate (in one paragraph) which categories are strong and which are weak, and why

### Gotchas

- **Don't let the LLM write your eval set.** It'll generate questions the model happens to answer well. Ground truth means you verified against the corpus with your own eyes.
- Judge bias: if you use Claude Sonnet as both generator and judge, faithfulness will be inflated. Use Haiku for the judge.
- If Hit@5 is < 0.6 on factual_lookup, your chunking is broken. Go back to Phase 2 before running generation evals.
- If faithfulness > 0.95 on first run, either you're lucky or your judge is too lenient. Spot-check 5 cases by hand.

---

## Phase 6 — One meaningful improvement (cross-encoder reranking)

**Goal:** Measurable improvement (or honest null result) from cross-encoder reranking.

**Time:** 3–4 hours

### Tasks

1. Add `BAAI/bge-reranker-base` as a new dependency.
2. Modify the retriever: optionally fetch top-20, rerank with cross-encoder, return top-5.
3. Wire a config flag (`settings.rerank_enabled`) so you can flip it.
4. Run the eval in both modes.
5. Populate the full README table.
6. Write `docs/decisions/0002-reranking.md` — one-page ADR with the result, your interpretation, and what you'd try next.

**If reranking doesn't help** (this happens on small corpora), that's a real engineering finding. Write about it honestly. "Reranking reduced Hit@5 by 3pp; hypothesis: the base retriever was already near ceiling on this corpus size. Next step: hybrid BM25 + vector." That reads as more senior than a contrived win.

### Cursor prompt

```
Add cross-encoder reranking to DocuMate.

Changes:
- backend/app/services/reranker.py (new): wraps BAAI/bge-reranker-base via sentence-transformers CrossEncoder. rerank(query, chunks) -> reordered chunks. Lives under app/services because the API also uses it at query time.
- backend/app/services/retriever.py: accept a reranker (optional). If provided: fetch top-20, rerank, return top-5.
- backend/app/config.py: add rerank_enabled: bool = False, rerank_candidates: int = 20.
- backend/evals/configs/reranked.yaml (new): copy baseline.yaml, set rerank_enabled=true, rerank_candidates=20.
- backend/evals/run_eval.py: --config reranked loads backend/evals/configs/reranked.yaml.
- docs/decisions/0002-reranking.md (new): ADR template — leave the "Result" and "Decision" sections for me to fill in after the eval runs.

Re-run eval:
- make eval (baseline)
- make eval-rerank (reranked, with --compare-to baseline; emits a diff)

The diff table baseline vs reranked across all metrics and categories should be in the reranked report's `.md`. Flag any regressions.

Don't interpret the results for me — just surface the numbers. I'll write the ADR interpretation.
```

### Definition of Done

- [ ] `backend/evals/reports/reranked_*.md` exists with a baseline-vs-reranked diff
- [ ] README table fully populated
- [ ] `docs/decisions/0002-reranking.md` written (by you, not by Claude)
- [ ] You have a 30-second verbal answer to "walk me through what you tried and what happened"

### Gotchas

- Reranker adds ~500ms latency per query. Include that in your latency numbers — don't hide it.
- If reranking helps on factual_lookup but hurts on multi-hop, that's a real and interesting finding. Don't average it away.

---

## Phase 7 — Deploy

**Goal:** Live URL. Backend on Fly.io, frontend on Vercel.

**Time:** 3–5 hours. **This will fight you.** Plan for it.

### Sub-phase 7a — Backend to Fly.io

1. Write `infra/Dockerfile` for FastAPI (multi-stage, slim python base, uv for install, non-root user). Pre-download the BGE model weights at build time (`RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"`) so cold-starts on Fly are fast.
2. `infra/fly.toml`:
   - `[mounts]` persistent volume at `/data` (Chroma lives here)
   - `[http_service]` on 8080, auto-stop, auto-start, min_machines_running = 0 (save money)
   - Healthcheck on `/health`
3. First deploy: build locally, ingest into the mounted volume, `fly deploy`. Or: bake the chroma db into the image for v1 (simpler, rebuild on corpus change).
4. Set secrets: `fly secrets set ANTHROPIC_API_KEY=...`
5. CORS: allow your Vercel domain only.

### Sub-phase 7b — Frontend to Vercel

1. `vercel.json` minimal; connect GitHub repo.
2. Env var: `API_URL` = your Fly app URL (used server-side only).
3. `NEXT_PUBLIC_APP_NAME` for display.
4. Deploy preview branch first, verify, then promote.

### Sub-phase 7c — Harden

- Add `slowapi` rate limit on `/chat`: 10 req/min per IP.
- Optional: require a `?key=X` query param (simple shared secret) so random scrapers don't burn your Anthropic credits. Put the key in the README as a "demo key: X" — friction is the goal, not security.
- Remove any personal data, API keys, absolute paths from the repo. Run `git secrets --scan` or `trufflehog` locally.

### Cursor prompt

```
Prepare DocuMate for deployment.

The repo already has `infra/` scaffolded (empty). Put Dockerfile and fly.toml there.

Backend (Fly.io):
- infra/Dockerfile: python:3.11-slim, multi-stage, uv install, non-root user, EXPOSE 8080, CMD uvicorn. Pre-download BGE weights at build time so cold-starts are fast.
- .dockerignore (repo root): exclude backend/tests/, backend/notebooks/, data/raw/, data/processed/, frontend/, .plans/, docs/ (chroma is mounted separately or baked in — I'll choose).
- infra/fly.toml: app name "documate-api", primary region "syd", persistent volume "documate_data" mounted at /data, http service on 8080, auto-stop/start, healthcheck /health.
- Add CORS middleware to backend/app/main.py: allow only origins in settings.cors_origins (comma-separated list from env).
- Add slowapi to backend/pyproject.toml. Add slowapi rate limiter on /chat: 10/minute by IP.
- Optional demo key gate: if settings.demo_key is set, /chat requires ?key=... matching.

Frontend (Vercel):
- frontend/next.config.ts: set output standalone isn't needed for Vercel.
- Env handling: API_URL (server-side only), NEXT_PUBLIC_APP_NAME, NEXT_PUBLIC_DEMO_KEY (passed to server route, not exposed to client bundle).
- frontend/app/api/chat/route.ts: append ?key=... to the FastAPI URL if demo key is set.
- README: add "Deploy your own" section with fly launch + vercel deploy steps.

Scripts:
- backend/scripts/bake_chroma.sh: runs ingest locally, tars data/chroma/, uploads to Fly volume via fly ssh sftp OR includes it in the image (decide and document).
- Makefile: deploy-api, deploy-web, deploy (runs both).

Output the Dockerfile and fly.toml first. I'll review both before you wire the CORS and rate limit.
```

### Definition of Done

- [ ] Live backend URL: `https://documate-api.fly.dev/health` returns 200
- [ ] Live frontend URL: answers a question end-to-end
- [ ] Asked a question from your phone on LTE (not wifi) and it worked
- [ ] Live URL in the README (replacing `[Live demo](#)`)
- [ ] Demo key documented if you added one
- [ ] Repo has no secrets committed

### Gotchas

- Fly's free tier scales to zero. First request after idle takes ~10s. Put a note in the UI: "Waking up server…" on first load.
- CORS will bite you. If the frontend can't talk to the backend, it's CORS 95% of the time. Check the Network tab for OPTIONS preflight.
- BGE embedder loads ~130MB of weights. Bake them into the image or let them download on cold boot (slower but smaller image).

---

## Phase 8 — Write-up + polish (the payoff)

**Goal:** Everything a reader needs to evaluate you is on the repo landing page within 2 minutes.

**Time:** 4–6 hours

### Tasks

1. **Architecture diagram** — Excalidraw, 20 minutes. Export as PNG to `docs/diagrams/architecture.png`. Boxes + arrows for: browser → Vercel → Fly → retriever → Chroma → generator → Anthropic. Annotate the reranker.
2. **Demo GIF** — record 30 seconds with QuickTime, convert with `ffmpeg -i demo.mov -vf "fps=10,scale=800:-1" demo.gif`. Under 5MB.
3. **ADRs** (one page each, 15 minutes each):
   - `docs/decisions/0001-no-langchain.md` — **already exists from Phase 0; review for accuracy, do not overwrite**
   - `docs/decisions/0002-reranking.md` (result + interpretation, written after Phase 6 eval)
   - `docs/decisions/0003-bge-over-openai-embeddings.md`
   - `docs/decisions/0004-haiku-as-judge.md`
4. **docs/evals.md** — already exists from Phase 0 with the methodology skeleton. Phase 8 fills in the actual results, observations, and a per-category breakdown after eval runs. This is the doc you'll point interviewers to.
5. **LinkedIn post** — 200 words. Problem → approach → result (one number) → link. No hashtag spam.
6. **CV bullet** — one line, update with real numbers.
7. **Cover letter paragraph** — tie DocuMate explicitly to the Atlassian JD's "Employee Productivity and Support" team.

### LinkedIn post template (edit to your voice)

```
I spent the last two weeks building DocuMate — a RAG-based internal knowledge
assistant for Fair Work Australia content, shipped end-to-end from scraper
to deployed Next.js UI.

The part I spent the most time on wasn't the retrieval or the generation. It
was the eval harness: 30 hand-crafted Q&A pairs across 6 categories, Hit@5,
MRR, LLM-as-judge faithfulness, and citation accuracy. Because without evals,
"my RAG works" is a vibe, not a result.

Baseline: Hit@5 = 0.XX, Faithfulness = 0.XX.
With cross-encoder reranking: Hit@5 = 0.XX, Faithfulness = 0.XX.

Stack: Python/FastAPI · ChromaDB · BGE-small local embeddings · Claude Sonnet
generator + Haiku judge · Next.js · Fly.io + Vercel. No LangChain.

Live demo + repo + full eval methodology in comments.
```

### Cover letter paragraph (for the Atlassian role)

```
To sharpen my generative AI engineering depth ahead of this conversation, I
recently built DocuMate, a RAG-based internal knowledge assistant over Fair
Work Australia content. Beyond the retrieval and generation pipeline, I
designed a category-stratified evaluation framework (Hit@5, MRR, LLM-as-judge
faithfulness, citation accuracy) and measured the impact of cross-encoder
reranking against a baseline. The repo, live demo, and eval methodology are
available at [link]. The shape of the problem — a production-grade GenAI tool
for employee productivity, with measurable quality — maps directly to the
Employee Productivity and Support remit described in this role.
```

### Cursor prompt

```
Finalize DocuMate documentation.

Create/update:
- docs/diagrams/architecture.png (I'll draw this in Excalidraw and drop it in)
- docs/diagrams/demo.gif (I'll record and convert)
- docs/decisions/0001-no-langchain.md — ALREADY EXISTS from Phase 0. Review and refresh only; do NOT overwrite.
- docs/decisions/0002-reranking.md (NEW)
- docs/decisions/0003-bge-over-openai-embeddings.md (NEW)
- docs/decisions/0004-haiku-as-judge.md (NEW)
- docs/evals.md — ALREADY EXISTS from Phase 0 with methodology skeleton. Update with Results, Observations, Limitations sections using real numbers from backend/evals/reports/.
- docs/architecture.md — ALREADY EXISTS with ASCII diagram placeholder. Embed the architecture.png and refresh component descriptions.
- README.md (fill placeholders: live demo URL, baseline numbers, reranked numbers, embed demo.gif and architecture.png)

ADR template (4-6 bullets each):
- Context: why this decision came up
- Options considered
- Decision: what we chose
- Consequences: what this costs us, what it buys us
- Revisit trigger: when we'd change our mind

docs/evals.md structure:
- Overview (2 paragraphs: what, why)
- Dataset: construction process, category definitions + counts, sample entry
- Metrics: formula for each, why chosen
- Judge: model, prompt, bias considerations
- Results: overall table, per-category table, baseline vs reranked
- Observations: 3-5 findings (be honest about weaknesses)
- Limitations: sample size, judge reliance, corpus scope
- What we'd do next

Do not invent numbers. Use placeholders like {HIT_AT_5_BASELINE} — I will fill them in from reports/.
```

### Definition of Done

- [ ] README tells the full story without scrolling through code
- [ ] Architecture diagram readable at thumbnail size
- [ ] Demo GIF < 5MB, autoplays
- [ ] All 4 ADRs written
- [ ] `docs/evals.md` is something you'd hand to an interviewer
- [ ] LinkedIn post drafted (not posted yet)
- [ ] CV bullet and cover letter paragraph drafted

---

## Post-ship checklist (before you hit "Apply")

- [ ] Repo is public and pinned on your GitHub profile
- [ ] LinkedIn post published with repo + live demo links
- [ ] CV updated with DocuMate bullet under "Projects"
- [ ] Cover letter paragraph inserted, tailored to the Atlassian JD
- [ ] You've done a dry run explaining the project in 2 minutes out loud (record yourself if you have to)
- [ ] You've done a dry run of the 5 questions most likely to come up:
  1. Why Chroma over pgvector/Qdrant?
  2. Why BGE over OpenAI embeddings?
  3. Walk me through your eval methodology.
  4. What did reranking buy you? Why do you think?
  5. What's the weakest part of this system?
- [ ] You've reached out to a contact at the target company (Atlassian) informally before applying cold

---

## Anti-goals (things to NOT do)

- **Don't add agents.** This is a RAG, not an agent. Stay in your lane.
- **Don't fine-tune anything.** Out of scope and out of budget.
- **Don't add authentication.** Demo key is enough.
- **Don't rewrite your eval set after seeing results.** That's overfitting to your own benchmark.
- **Don't hide weak results.** If reranking didn't help, say so. "Honest null result + interpretation" > "contrived win".
- **Don't use LangChain because a tutorial uses it.** Your ground rules forbid it for a reason: the interviewer can ask "what does this line actually do" and your answer has to be precise.
- **Don't exceed 10 elapsed days.** Ship > perfect. You can iterate post-application.

---

## Common failure modes (and what to do)

| Symptom | Likely cause | Fix |
|---|---|---|
| Hit@5 < 0.5 on factual_lookup | Chunking broke document semantics | Revisit Phase 2 chunker; check heading splits |
| Faithfulness > 0.95 out of the gate | Judge is too lenient or prompt isn't strict | Tighten judge rubric; spot-check 5 cases by hand |
| Faithfulness < 0.6 | Generator prompt not enforcing "only from context" | Add few-shot examples to the prompt; lower temperature to 0 |
| Rerank hurts metrics | Base retriever was ceiling; or top-20 pool too noisy | Try top-10 rerank input; or pivot to hybrid BM25 |
| Fly cold starts take 30s | BGE weights downloading at boot | Bake into image; or move to always-on (costs $) |
| CORS errors in prod | Backend CORS list doesn't include Vercel domain | Check OPTIONS preflight in Network tab |
| Citations cite chunk IDs not in retrieved set | Model hallucinating IDs | Post-process: filter to retrieved set; log the drop rate as a quality signal |

---

*Use this doc as your project bible. Update the DoD checkboxes as you go. When you hit Phase 8, you'll have earned the right to apply to the Atlassian role.*