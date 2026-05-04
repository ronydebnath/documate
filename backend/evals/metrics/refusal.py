"""Refusal / clarification behavior check for out_of_scope and ambiguous categories."""

from __future__ import annotations

from app.prompts.answer import REFUSAL_PHRASE

# Cheap heuristic clarifier markers. Phase 5 uses string matching only;
# Phase 6+ can swap to a Haiku judge call if these prove unreliable.
_CLARIFIER_MARKERS = (
    "could you",
    "do you mean",
    "which",
    "more specifically",
    "clarify",
    "what kind",
    "what type",
    "can you specify",
)


def refusal_correct(category: str, answer: str) -> bool | None:
    """Returns True/False for out_of_scope and ambiguous; None for everything else.

    out_of_scope: the answer must contain the exact refusal phrase as a substring.
    ambiguous:    the answer must contain a question mark and at least one clarifier marker.
    """
    if category == "out_of_scope":
        return REFUSAL_PHRASE in (answer or "")
    if category == "ambiguous":
        a = (answer or "").lower()
        return "?" in a and any(m in a for m in _CLARIFIER_MARKERS)
    return None
