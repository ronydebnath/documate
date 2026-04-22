# Architecture

> _Diagram placeholder — export an Excalidraw sketch to `docs/diagrams/architecture.png` and embed here._

## Components

```
  Source docs (Fair Work HTML)
            │
            ▼
     ┌─────────────┐     ┌────────────┐     ┌──────────┐
     │  Ingestion  │────▶│  Embedder  │────▶│ ChromaDB │
     │  (batch CLI)│     │ (OpenAI)   │     │  (local) │
     └─────────────┘     └────────────┘     └────┬─────┘
                                                 │
                  ┌──────────────────────────────┘
                  ▼
     ┌────────────────────┐     ┌─────────────────┐     ┌─────────────────┐
     │  Retriever          │────▶│ Generator       │────▶│ FastAPI /chat  │
     │  (top-k, optional   │     │ (Claude Sonnet, │     │                 │
     │   cross-enc rerank) │     │  prompt + cite) │     │                 │
     └────────────────────┘     └─────────────────┘     └────────┬────────┘
                                                                  │
                                                                  ▼
                                                        ┌─────────────────┐
                                                        │ Next.js chat UI │
                                                        └─────────────────┘
```

## Deploy topology

- **Backend:** Fly.io (Dockerfile in `infra/`). Single process, FastAPI + Uvicorn. Chroma persists to a Fly volume.
- **Frontend:** Vercel (standard Next.js deploy). Calls backend via `NEXT_PUBLIC_BACKEND_URL`.
- **Data:** Corpus is baked into the backend image at build time for the portfolio demo. For a production system this would be decoupled.

## Key design decisions

See [decisions/](./decisions/) — lightweight ADRs.

- [ADR-0001: No LangChain](./decisions/0001-no-langchain.md)
- Further ADRs to be added as decisions are made (chunking strategy, reranker choice, refusal behavior).
