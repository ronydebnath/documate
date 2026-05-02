"""Retriever: query Chroma with a BGE-prefixed query embedding."""

from __future__ import annotations

from dataclasses import dataclass

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


class Retriever:
    def __init__(self, store: ChromaStore):
        self._store = store

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        if not query.strip():
            return []
        # embed_query already applies the BGE retrieval prefix; do not re-prefix.
        qvec = embed_query(query)
        res = self._store.query(qvec, top_k=top_k)

        ids = res.get("ids", [[]])[0]
        documents = res.get("documents", [[]])[0]
        metadatas = res.get("metadatas", [[]])[0]
        distances = res.get("distances", [[]])[0]

        out: list[RetrievedChunk] = []
        for cid, doc, meta, dist in zip(ids, documents, metadatas, distances):
            meta = meta or {}
            out.append(
                RetrievedChunk(
                    chunk_id=cid,
                    text=doc or "",
                    title=meta.get("title", ""),
                    source_url=meta.get("source_url", ""),
                    section=meta.get("section", ""),
                    distance=float(dist),
                )
            )
        return out
