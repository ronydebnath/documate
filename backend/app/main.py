"""FastAPI app for DocuMate.

Run via: `cd backend && uv run uvicorn app.main:app --reload`
or `make backend`.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import get_settings
from app.routes import chat as chat_route
from app.routes import health as health_route
from app.services.chat_service import ChatService
from app.services.generator import Generator
from app.services.retriever import Retriever
from ingest.chroma_store import ChromaStore


def _split_origins(raw: str) -> list[str]:
    return [o.strip() for o in raw.split(",") if o.strip()]


def _rate_limit_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )


def create_app() -> FastAPI:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    s = get_settings()

    limiter = Limiter(key_func=get_remote_address, default_limits=[])

    app = FastAPI(title="DocuMate API", version="0.1.0")
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)

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
    app.state.demo_key = s.demo_key
    app.state.chat_rate_limit = s.chat_rate_limit

    app.include_router(health_route.router)
    app.include_router(chat_route.router)

    return app


app = create_app()
