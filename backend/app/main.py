"""FastAPI app for DocuMate.

Run via: `cd backend && uv run uvicorn app.main:app --reload`
or `make backend`.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import chat as chat_route
from app.routes import health as health_route
from app.services.chat_service import ChatService
from app.services.generator import Generator
from app.services.retriever import Retriever
from ingest.chroma_store import ChromaStore


def _split_origins(raw: str) -> list[str]:
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_app() -> FastAPI:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    s = get_settings()

    app = FastAPI(title="DocuMate API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_split_origins(s.cors_allowed_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Wire dependencies once at startup. Embedder/reranker lazy-load on first call.
    store = ChromaStore(s.chroma_persist_dir, s.chroma_collection)
    rerank_fn = None
    if s.reranker_enabled:
        from app.services.reranker import rerank as rerank_fn  # imported only when enabled

    retriever = Retriever(
        store,
        reranker=rerank_fn,
        rerank_candidates=s.rerank_candidates,
    )
    generator = Generator(
        api_key=s.anthropic_api_key,
        model=s.anthropic_generator_model,
    )
    chat_service = ChatService(
        retriever=retriever,
        generator=generator,
        top_k=s.retrieval_top_k,
    )

    app.state.store = store
    app.state.chat_service = chat_service

    app.include_router(health_route.router)
    app.include_router(chat_route.router)

    return app


app = create_app()
