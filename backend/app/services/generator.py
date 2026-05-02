"""Claude Sonnet generator. Pure: prompt in, answer + parsed citations out."""

from __future__ import annotations

import re
from dataclasses import dataclass

import anthropic

# Matches the chunk_id format produced by the ingest pipeline:
#   {doc_slug}::{ordinal:04d}
# where doc_slug is lowercase letters, digits, and hyphens.
CITATION_RE = re.compile(r"\[([a-z0-9][a-z0-9-]*::\d{4})\]")


@dataclass(frozen=True)
class AnswerWithCitations:
    text: str
    cited_chunk_ids: list[str]


def parse_citations(text: str) -> list[str]:
    """Pull [chunk_id] citations out of an answer, deduplicated, in first-occurrence order."""
    cited: list[str] = []
    seen: set[str] = set()
    for m in CITATION_RE.finditer(text or ""):
        cid = m.group(1)
        if cid not in seen:
            seen.add(cid)
            cited.append(cid)
    return cited


class Generator:
    def __init__(self, api_key: str, model: str, max_tokens: int = 1024):
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is empty. Set it in .env before starting the API."
            )
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, system: str, user: str) -> AnswerWithCitations:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = ""
        for block in resp.content or []:
            block_text = getattr(block, "text", None)
            if block_text:
                text += block_text
        return AnswerWithCitations(text=text, cited_chunk_ids=parse_citations(text))
