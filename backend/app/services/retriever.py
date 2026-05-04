"""Retriever: query Chroma with a BGE-prefixed query embedding.

When `rerank_candidates > 0`, the Retriever fetches that many candidates
from Chroma and passes them to the (optional) cross-encoder reranker for
reordering before returning the top_k. The reranker is injected by the
caller so this module stays composable and testable in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.services.embedder import embed_query
from ingest.chroma_store import ChromaStore


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    title: str
    source_url: str
    section: str
    distance: float


# Reranker function shape: (query, chunks, top_k) -> reordered chunks
RerankFn = Callable[[str, list["RetrievedChunk"], int], list["RetrievedChunk"]]


class Retriever:
    def __init__(
        self,
        store: ChromaStore,
        reranker: RerankFn | None = None,
        rerank_candidates: int = 20,
    ):
        self._store = store
        self._reranker = reranker
        self._rerank_candidates = rerank_candidates

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        if not query.strip():
            return []
        # embed_query already applies the BGE retrieval prefix; do not re-prefix.
        qvec = embed_query(query)

        # Fetch a wider candidate pool if reranking; otherwise just top_k.
        fetch_k = max(self._rerank_candidates, top_k) if self._reranker else top_k
        res = self._store.query(qvec, top_k=fetch_k)

        ids = res.get("ids", [[]])[0]
        documents = res.get("documents", [[]])[0]
        metadatas = res.get("metadatas", [[]])[0]
        distances = res.get("distances", [[]])[0]

        candidates: list[RetrievedChunk] = []
        for cid, doc, meta, dist in zip(ids, documents, metadatas, distances):
            meta = meta or {}
            candidates.append(
                RetrievedChunk(
                    chunk_id=cid,
                    text=doc or "",
                    title=meta.get("title", ""),
                    source_url=meta.get("source_url", ""),
                    section=meta.get("section", ""),
                    distance=float(dist),
                )
            )

        if self._reranker is None:
            return candidates[:top_k]
        # Rerank inside retrieve() so the latency is correctly attributed
        # to retrieve_ms by ChatService and the eval harness.
        return self._reranker(query, candidates, top_k)
