"""Cross-encoder reranker, lazy-loaded singleton.

Wraps `BAAI/bge-reranker-base` via sentence-transformers' CrossEncoder.
Used by the Retriever when `settings.reranker_enabled` is True: fetch
top-N candidates from Chroma, score each (query, chunk) pair with the
cross-encoder, return the top-K by score.

First call downloads ~280MB of weights. Single-threaded; CPU is fine for
top-20 candidates per query (~500ms warm).
"""

from __future__ import annotations

from typing import Iterable, Protocol

from sentence_transformers import CrossEncoder

from app.config import get_settings

_model: CrossEncoder | None = None


class _ChunkLike(Protocol):
    chunk_id: str
    text: str


def _get_model() -> CrossEncoder:
    global _model
    if _model is None:
        s = get_settings()
        _model = CrossEncoder(s.reranker_model, device=s.embedding_device)
    return _model


def rerank(query: str, chunks: list, top_k: int) -> list:
    """Score (query, chunk.text) pairs with the cross-encoder and return the
    top_k chunks reordered by descending score.

    `chunks` must expose `.text` and is otherwise opaque (typed as `_ChunkLike`).
    Returns the same chunk objects, sliced to `top_k`, in score order.
    """
    if not chunks or top_k <= 0:
        return []
    if len(chunks) <= top_k and len(chunks) <= 1:
        # Trivially nothing to reorder.
        return chunks[:top_k]

    model = _get_model()
    pairs = [(query, c.text) for c in chunks]
    scores = model.predict(pairs, show_progress_bar=False).tolist()
    # Stable sort by descending score; preserve original order on ties.
    order = sorted(range(len(chunks)), key=lambda i: (-scores[i], i))
    return [chunks[i] for i in order[:top_k]]
