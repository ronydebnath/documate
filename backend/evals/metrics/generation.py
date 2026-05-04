"""Generation metrics: citation F1 and must_contain pass."""

from __future__ import annotations

from evals.metrics.retrieval import slug_of_chunk_id, slug_of_expected


def citation_f1(
    cited_chunk_ids: list[str], expected_source_ids: list[str]
) -> tuple[float, float, float]:
    """Set-based precision/recall/F1 on slug overlap.

    - both empty (no expectation, nothing cited)            -> (1, 1, 1)
    - cited empty but expected non-empty                    -> (0, 0, 0)
    - expected empty but cited non-empty                    -> (0, 0, 0)  (over-citing where none was wanted)
    - otherwise                                             -> standard F1 on slug-set intersection
    """
    cited = {slug_of_chunk_id(c) for c in cited_chunk_ids}
    expected = {slug_of_expected(e) for e in expected_source_ids}

    if not cited and not expected:
        return 1.0, 1.0, 1.0
    if not cited or not expected:
        return 0.0, 0.0, 0.0

    overlap = cited & expected
    precision = len(overlap) / len(cited)
    recall = len(overlap) / len(expected)
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return precision, recall, f1


def must_contain_pass(
    answer: str, must_contain: list[str], must_not_contain: list[str]
) -> bool:
    """Case-insensitive substring guards.

    Returns True iff every required string is present AND no forbidden string is present.
    Empty lists trivially pass.
    """
    a = (answer or "").lower()
    for s in must_contain:
        if (s or "").lower() not in a:
            return False
    for s in must_not_contain:
        if (s or "").lower() in a:
            return False
    return True
