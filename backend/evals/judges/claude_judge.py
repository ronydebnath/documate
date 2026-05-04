"""LLM-as-judge for faithfulness, using Claude Haiku.

Uses Anthropic tool_use to enforce the JSON schema. Failures (network,
schema mismatch, empty content) return faithful=0 with a parse_error so
the run never crashes. Temperature 0.

Run cost is ~$0.0005 per case at Haiku pricing; 30-case eval ≈ $0.015.
"""

from __future__ import annotations

import json
from typing import Iterable, Protocol

import anthropic

from evals.schemas import JudgeVerdict


class _ChunkLike(Protocol):
    chunk_id: str
    title: str
    text: str


_SYSTEM = (
    "You are evaluating whether an AI answer is grounded in provided source material. "
    "Be strict. Only mark a claim as supported if the source material contains the "
    "information, even if worded differently. Mark a claim as unsupported if it adds "
    "information not present in the source, including plausible-but-ungrounded details."
)

_TOOL_NAME = "record_faithfulness"

_TOOL_SCHEMA = {
    "name": _TOOL_NAME,
    "description": "Record the faithfulness verdict for one answer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "faithful": {
                "type": "integer",
                "enum": [0, 1],
                "description": "1 only if every claim in the answer is supported by the source. 0 otherwise.",
            },
            "unsupported_claims": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of specific claims in the answer that are not supported by the source.",
            },
            "reason": {
                "type": "string",
                "description": "One-line summary of the verdict.",
            },
        },
        "required": ["faithful", "unsupported_claims", "reason"],
    },
}


def _build_user_message(
    question: str, answer: str, chunks: Iterable[_ChunkLike]
) -> str:
    blocks: list[str] = []
    for c in chunks:
        safe_title = (c.title or "").replace("<", "").replace(">", "")
        blocks.append(
            f'<chunk id="{c.chunk_id}" source="{safe_title}">\n{c.text}\n</chunk>'
        )
    source_material = "\n".join(blocks) if blocks else "(no source chunks)"
    return (
        "<source_material>\n"
        f"{source_material}\n"
        "</source_material>\n\n"
        f"<question>{question}</question>\n\n"
        f"<answer>{answer}</answer>\n\n"
        "<task>\n"
        "Use the record_faithfulness tool to record your verdict.\n"
        "faithful = 1 only if unsupported_claims is empty.\n"
        "</task>"
    )


class ClaudeJudge:
    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5-20251001",
        max_tokens: int = 1024,
    ):
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is empty; judge cannot run.")
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def judge(
        self, question: str, answer: str, chunks: Iterable[_ChunkLike]
    ) -> JudgeVerdict:
        user = _build_user_message(question, answer, chunks)
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=0,
                system=_SYSTEM,
                tools=[_TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=[{"role": "user", "content": user}],
            )
        except Exception as e:
            return JudgeVerdict(
                faithful=0,
                reason="judge_api_error",
                parse_error=f"{type(e).__name__}: {e}",
            )

        # Locate the tool_use block
        for block in resp.content or []:
            if getattr(block, "type", None) != "tool_use":
                continue
            if getattr(block, "name", None) != _TOOL_NAME:
                continue
            payload = getattr(block, "input", None) or {}
            try:
                # Normalize: payload may already be a dict (typical) or json text.
                if isinstance(payload, str):
                    payload = json.loads(payload)
                faithful = int(payload.get("faithful", 0))
                claims = list(payload.get("unsupported_claims", []) or [])
                reason = str(payload.get("reason", "") or "")
                return JudgeVerdict(
                    faithful=1 if faithful == 1 and not claims else 0,
                    unsupported_claims=claims,
                    reason=reason,
                    parse_error=None,
                )
            except Exception as e:
                return JudgeVerdict(
                    faithful=0,
                    reason="judge_parse_error",
                    parse_error=f"{type(e).__name__}: {e}",
                )

        return JudgeVerdict(
            faithful=0,
            reason="no_tool_use_in_response",
            parse_error="judge response contained no tool_use block",
        )
