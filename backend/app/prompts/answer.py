"""Versioned answer prompt for DocuMate.

The system prompt is stable across requests (Anthropic caches it). The user
message carries the dynamic context + question.

PROMPT_VERSION is recorded by the eval harness so before/after results stay
reproducible when the prompt changes.
"""

from __future__ import annotations

from typing import Iterable, Protocol

PROMPT_VERSION = "v1"

REFUSAL_PHRASE = (
    "I don't have information on that in the Fair Work documents I have access to."
)

SYSTEM_PROMPT = f"""<role>You are a Fair Work Australia information assistant.</role>

<instructions>
- Answer only from the provided context.
- Cite every claim using [chunk_id] inline after the relevant sentence. The chunk_id is the exact value in the chunk's id attribute.
- If the context does not contain the answer, say exactly: "{REFUSAL_PHRASE}"
- Never invent chunk IDs. Never cite chunks not in the context.
- Be concise. Maximum 4 sentences unless the question requires a list.
- Use Australian English.
- Do not give legal advice; direct users to the Fair Work Ombudsman for personal situations.
</instructions>"""


class _ChunkLike(Protocol):
    chunk_id: str
    title: str
    text: str


def build_user_message(query: str, chunks: Iterable[_ChunkLike]) -> str:
    """Compose the user message: <context> + <question>."""
    blocks: list[str] = []
    for c in chunks:
        # Strip any stray angle brackets in the title to avoid breaking the XML wrap.
        safe_title = (c.title or "").replace("<", "").replace(">", "")
        blocks.append(
            f'<chunk id="{c.chunk_id}" source="{safe_title}">\n{c.text}\n</chunk>'
        )
    context = "\n".join(blocks) if blocks else "(no documents matched)"
    return (
        "<context>\n"
        f"{context}\n"
        "</context>\n\n"
        "<question>\n"
        f"{query}\n"
        "</question>"
    )
