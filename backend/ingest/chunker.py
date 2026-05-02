"""Recursive text splitter for DocuMate.

Pure function: text in, list of Chunks out. No I/O. No model. No LangChain.

Splits in priority order: heading boundaries → paragraph blank lines →
sentence endings → character window. Greedy-packs atomic units up to a token
target, then carries an overlap of trailing tokens into the next chunk.

Token counts use tiktoken cl100k_base — the de-facto chunking tokenizer; it
diverges from Claude's tokenizer by a few percent but that's well within the
slack we want anyway.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken

_ENC = tiktoken.get_encoding("cl100k_base")

# Splitters at line start. We check `\n` + marker so we only match real
# heading lines, not "#" inside prose.
_HEADING_RE = re.compile(r"\n(?=#{1,6}\s)")
_PARAGRAPH_RE = re.compile(r"\n\s*\n")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"'])")


@dataclass(frozen=True)
class Chunk:
    text: str
    char_start: int
    char_end: int
    token_count: int


def _count_tokens(text: str) -> int:
    return len(_ENC.encode(text))


def _split_with_offsets(text: str, base: int, pattern: re.Pattern) -> list[tuple[str, int]]:
    """Split `text` by `pattern`, returning (piece, char_start_in_full_doc) tuples.
    `base` is the offset of `text` within the original full document.
    """
    if not text:
        return []
    pieces: list[tuple[str, int]] = []
    cursor = 0
    for m in pattern.finditer(text):
        piece = text[cursor:m.start()]
        if piece.strip():
            pieces.append((piece, base + cursor))
        cursor = m.end()
    tail = text[cursor:]
    if tail.strip():
        pieces.append((tail, base + cursor))
    return pieces


def _atomic_units(text: str, target_tokens: int) -> list[tuple[str, int]]:
    """Recursively split until each unit fits in target_tokens on its own.

    Order: headings → paragraphs → sentences → token-aware character window.
    Token-aware fallback uses binary search on character length so a pathological
    input (e.g. " ".join("x" * N)) doesn't blow past the budget — chars-per-token
    varies wildly with content.
    """
    return _split_recursive(text, 0, target_tokens)


def _split_recursive(text: str, base: int, target_tokens: int) -> list[tuple[str, int]]:
    pieces = _split_with_offsets(text, base, _HEADING_RE)
    if len(pieces) <= 1:
        pieces = _split_with_offsets(text, base, _PARAGRAPH_RE)
    if len(pieces) <= 1:
        pieces = _split_with_offsets(text, base, _SENTENCE_RE)
    if len(pieces) <= 1:
        return _split_by_token_window(text, base, target_tokens)

    # Some pieces may themselves still be larger than target_tokens; recurse.
    expanded: list[tuple[str, int]] = []
    for piece, off in pieces:
        if _count_tokens(piece) > target_tokens:
            expanded.extend(_split_recursive(piece, off, target_tokens))
        else:
            expanded.append((piece, off))
    return expanded


def _split_by_token_window(
    text: str, base: int, target_tokens: int
) -> list[tuple[str, int]]:
    """Slice `text` into pieces of <= target_tokens each, by binary-searching
    for the largest character span whose token count fits the budget.
    """
    if not text.strip():
        return []
    if _count_tokens(text) <= target_tokens:
        return [(text, base)]

    out: list[tuple[str, int]] = []
    cursor = 0
    n = len(text)
    while cursor < n:
        lo, hi = cursor + 1, n
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if _count_tokens(text[cursor:mid]) <= target_tokens:
                lo = mid
            else:
                hi = mid - 1
        chunk_end = max(lo, cursor + 1)
        piece = text[cursor:chunk_end]
        if piece.strip():
            out.append((piece, base + cursor))
        if chunk_end <= cursor:
            break
        cursor = chunk_end
    return out


def chunk_text(
    text: str,
    target_tokens: int = 500,
    overlap_tokens: int = 50,
) -> list[Chunk]:
    """Greedy-pack atomic units into chunks of ~target_tokens with overlap_tokens overlap."""
    if not text or not text.strip():
        return []

    units = _atomic_units(text, target_tokens)
    if not units:
        return []

    chunks: list[Chunk] = []
    buf: list[tuple[str, int]] = []  # accumulated (text, char_start) pieces
    buf_tokens = 0

    def emit() -> None:
        if not buf:
            return
        joined = "".join(p[0] for p in buf).strip()
        if not joined:
            return
        c_start = buf[0][1]
        last_text, last_off = buf[-1]
        c_end = last_off + len(last_text)
        # Re-derive offsets from the original by trimming whitespace
        # consistently: use the un-stripped concatenation length and adjust.
        raw_join = "".join(p[0] for p in buf)
        leading_ws = len(raw_join) - len(raw_join.lstrip())
        trailing_ws = len(raw_join) - len(raw_join.rstrip())
        chunks.append(Chunk(
            text=joined,
            char_start=c_start + leading_ws,
            char_end=c_end - trailing_ws,
            token_count=_count_tokens(joined),
        ))

    for piece_text, piece_off in units:
        piece_tokens = _count_tokens(piece_text)
        if buf_tokens + piece_tokens > target_tokens and buf:
            emit()
            # Carry overlap: take trailing tokens from the last buf piece.
            if overlap_tokens > 0 and buf:
                last_text, last_off = buf[-1]
                last_token_ids = _ENC.encode(last_text)
                if len(last_token_ids) > overlap_tokens:
                    keep_ids = last_token_ids[-overlap_tokens:]
                    keep_text = _ENC.decode(keep_ids)
                    # Find keep_text at end of last_text to recover its offset.
                    idx = last_text.rfind(keep_text)
                    if idx == -1:
                        # Decoder might re-encode whitespace; fall back to length-based offset.
                        idx = max(0, len(last_text) - len(keep_text))
                    buf = [(keep_text, last_off + idx)]
                    buf_tokens = _count_tokens(keep_text)
                else:
                    # Last piece is smaller than overlap; carry the whole thing.
                    buf = [buf[-1]]
                    buf_tokens = _count_tokens(buf[0][0])
            else:
                buf = []
                buf_tokens = 0
        buf.append((piece_text, piece_off))
        buf_tokens += piece_tokens

    emit()
    return chunks
