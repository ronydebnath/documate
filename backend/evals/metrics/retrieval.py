"""Retrieval metrics: hit@k and MRR via slug-prefix matching.

A retrieved chunk_id like 'leave-parental-leave::0003' counts as a hit if
the slug 'leave-parental-leave' appears in expected_source_ids (after
stripping the optional 'fairwork/' namespace from each expected entry).

Slug-level matching means we don't have to rewrite the dataset every time
the chunker parameters change.
"""

from __future__ import annotations


def slug_of_chunk_id(chunk_id: str) -> str:
    """'leave-parental-leave::0003' -> 'leave-parental-leave'."""
    return chunk_id.split("::", 1)[0]


def slug_of_expected(expected_id: str) -> str:
    """'fairwork/leave-parental-leave' -> 'leave-parental-leave' (passes through unchanged when no namespace)."""
    return expected_id.split("/", 1)[1] if "/" in expected_id else expected_id


def expected_slug_set(expected_source_ids: list[str]) -> set[str]:
    return {slug_of_expected(e) for e in expected_source_ids}


def hit_at_k(retrieved_chunk_ids: list[str], expected_source_ids: list[str]) -> int:
    if not expected_source_ids:
        # Caller should not invoke this; defensive default.
        return 0
    expected = expected_slug_set(expected_source_ids)
    for cid in retrieved_chunk_ids:
        if slug_of_chunk_id(cid) in expected:
            return 1
    return 0


def mrr(retrieved_chunk_ids: list[str], expected_source_ids: list[str]) -> float:
    if not expected_source_ids:
        return 0.0
    expected = expected_slug_set(expected_source_ids)
    for i, cid in enumerate(retrieved_chunk_ids, start=1):
        if slug_of_chunk_id(cid) in expected:
            return 1.0 / i
    return 0.0
