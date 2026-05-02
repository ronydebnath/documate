"""BGE embeddings, lazy-loaded singleton.

Single source of truth for both ingest (write side) and retriever (query side).
The asymmetric prefix is enforced by the API surface — `embed_query` always
applies the BGE retrieval prefix; `embed_documents` never does. Callers can't
get this wrong by accident.

See ADR-0003 (planned) for why we use BGE locally instead of OpenAI embeddings.
"""

from __future__ import annotations

from typing import Any

from sentence_transformers import SentenceTransformer

from app.config import get_settings

# BGE retrieval-side instruction prefix. Documents do NOT get this prefix.
# Source: https://huggingface.co/BAAI/bge-small-en-v1.5#usage
_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_DEFAULT_BATCH_SIZE = 32

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Lazy-load the model once per process. First call downloads ~120MB."""
    global _model
    if _model is None:
        s = get_settings()
        _model = SentenceTransformer(s.embedding_model, device=s.embedding_device)
    return _model


def _encode(
    texts: list[str],
    batch_size: int = _DEFAULT_BATCH_SIZE,
    show_progress_bar: bool = False,
) -> list[list[float]]:
    """Internal: encode + L2-normalize a batch of texts."""
    model = _get_model()
    vectors: Any = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=show_progress_bar,
        convert_to_numpy=True,
    )
    return vectors.tolist()


def embed_documents(
    texts: list[str],
    batch_size: int = _DEFAULT_BATCH_SIZE,
    show_progress_bar: bool = True,
) -> list[list[float]]:
    """Embed document/chunk text. NO instruction prefix.

    Used by the ingest pipeline. Default batch size 32; default progress bar on
    because ingest runs are long.
    """
    if not texts:
        return []
    return _encode(texts, batch_size=batch_size, show_progress_bar=show_progress_bar)


def embed_query(text: str) -> list[float]:
    """Embed a query. Prepends the BGE retrieval prefix.

    Used by the retriever. Single-text path; no progress bar.
    """
    return _encode([_QUERY_PREFIX + text], batch_size=1, show_progress_bar=False)[0]


def embedding_dim() -> int:
    """Dimension of the loaded model's output. 384 for bge-small-en-v1.5."""
    return _get_model().get_sentence_embedding_dimension()
