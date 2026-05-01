# DocuMate — project rules for AI assistants

You are helping build DocuMate, a Fair Work Australia RAG assistant.

## Non-negotiables

- No LangChain, LlamaIndex, or agent frameworks. Direct SDK calls only.
- Python 3.11+, uv for deps, make for tasks. Backend lives under `backend/`.
- Next.js 14+ App Router, TypeScript, Tailwind, pnpm. Frontend lives under `frontend/`.
- Embeddings: `BAAI/bge-small-en-v1.5` via sentence-transformers (local, CPU). One implementation in `backend/app/services/embedder.py`, imported by both ingest and the API.
- Vector store: ChromaDB, file-backed at `data/chroma/`.
- Generator: `claude-sonnet-4-6`. Judge: `claude-haiku-4-5-20251001`. Never use `claude-sonnet-4-7` — that identifier belongs to Opus and will fail at runtime.
- Pydantic v2 for all schemas. No dict-shaped APIs.
- Every module has a single responsibility. `retriever.py` retrieves; it does not generate.
- Tests are pytest, under `backend/tests/`. Frontend tests, if any, under `frontend/__tests__/`.
- When asked for code, output a plan first if the change touches 3+ files. Wait for go-ahead.
- No emojis in code or logs. No em-dashes in generated docs.

## Source of truth

The build plan is [.plans/build_plan.md](.plans/build_plan.md). Treat it as the source of truth for scope and phase boundaries. Do not regenerate work from earlier phases — if a file already exists from Phase 0/1/2, edit it; do not overwrite.

## Memory of completed work

- Phase 0 scaffolding is done. The repo tree, [README.md](README.md), [Makefile](Makefile), [.gitignore](.gitignore), [.env.example](.env.example), [LICENSE](LICENSE), [backend/pyproject.toml](backend/pyproject.toml), [backend/evals/dataset.yaml](backend/evals/dataset.yaml) (3 seed entries), [docs/evals.md](docs/evals.md), [docs/architecture.md](docs/architecture.md), and [docs/decisions/0001-no-langchain.md](docs/decisions/0001-no-langchain.md) all exist.
- The ingestion pipeline, retriever, generator, FastAPI app, and frontend chat UI do not yet exist. They are scoped in build_plan.md Phases 1–4.
