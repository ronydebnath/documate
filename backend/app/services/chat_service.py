"""Orchestrates retrieve → build prompt → generate → validate citations.

Times each step. Drops hallucinated chunk IDs. Returns a ChatResponse the
API route can serialize directly.
"""

from __future__ import annotations

import logging
import time

from app.prompts.answer import SYSTEM_PROMPT, build_user_message
from app.schemas import ChatResponse, Citation, LatencyInfo
from app.services.generator import Generator
from app.services.retriever import Retriever, RetrievedChunk

log = logging.getLogger(__name__)

_SNIPPET_CHARS = 200


def _snippet(text: str) -> str:
    return text.replace("\n", " ").strip()[:_SNIPPET_CHARS]


class ChatService:
    def __init__(self, retriever: Retriever, generator: Generator, top_k: int = 5):
        self._retriever = retriever
        self._generator = generator
        self._top_k = top_k

    def chat(self, query: str) -> ChatResponse:
        t0 = time.monotonic()
        chunks: list[RetrievedChunk] = self._retriever.retrieve(query, top_k=self._top_k)
        t1 = time.monotonic()

        system = SYSTEM_PROMPT
        user = build_user_message(query, chunks)
        result = self._generator.generate(system=system, user=user)
        t2 = time.monotonic()

        retrieved_ids = {c.chunk_id for c in chunks}
        chunk_by_id = {c.chunk_id: c for c in chunks}

        valid_ids: list[str] = []
        invalid_ids: list[str] = []
        for cid in result.cited_chunk_ids:
            (valid_ids if cid in retrieved_ids else invalid_ids).append(cid)
        if invalid_ids:
            log.warning(
                "Generator cited chunk IDs not in retrieved set: %s", invalid_ids
            )

        citations = [
            Citation(
                chunk_id=cid,
                source_url=chunk_by_id[cid].source_url,
                title=chunk_by_id[cid].title,
                snippet=_snippet(chunk_by_id[cid].text),
            )
            for cid in valid_ids
        ]

        return ChatResponse(
            answer=result.text,
            citations=citations,
            retrieved_chunk_ids=[c.chunk_id for c in chunks],
            latency_ms=LatencyInfo(
                retrieve=int((t1 - t0) * 1000),
                generate=int((t2 - t1) * 1000),
                total=int((t2 - t0) * 1000),
            ),
        )
