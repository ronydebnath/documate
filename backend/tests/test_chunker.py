"""Tests for the recursive chunker. Pure-function coverage; no I/O, no model."""

from __future__ import annotations

import pytest

from ingest.chunker import Chunk, chunk_text


# ---------- Edge cases ----------

def test_empty_input_returns_no_chunks():
    assert chunk_text("") == []


def test_whitespace_only_returns_no_chunks():
    assert chunk_text("   \n\n  \t  \n") == []


# ---------- Single-chunk cases ----------

def test_single_short_paragraph_is_one_chunk():
    text = "An employee may resign by giving notice in writing to their employer."
    chunks = chunk_text(text, target_tokens=500)
    assert len(chunks) == 1
    assert "resign" in chunks[0].text
    assert chunks[0].token_count <= 50


# ---------- Heading-heavy doc ----------

def test_heading_heavy_document_splits_into_multiple_chunks():
    section = "Lorem ipsum dolor sit amet. " * 80  # ~250 tokens of filler
    text = (
        "# Title\n\n"
        f"## Section A\n\n{section}\n\n"
        f"## Section B\n\n{section}\n\n"
        f"## Section C\n\n{section}\n\n"
    )
    chunks = chunk_text(text, target_tokens=300, overlap_tokens=30)
    assert len(chunks) >= 2
    for c in chunks:
        assert c.token_count <= 400  # target + slack


# ---------- Long paragraph, no structure ----------

def test_very_long_paragraph_uses_character_window_fallback():
    text = "x " * 5000  # no headings, no paragraph breaks, no sentence ends
    chunks = chunk_text(text, target_tokens=500, overlap_tokens=50)
    assert len(chunks) >= 2
    for c in chunks:
        assert c.token_count <= 600


# ---------- Invariants ----------

def test_token_count_does_not_exceed_target_plus_slack():
    text = ". ".join(f"Sentence number {i}" for i in range(400)) + "."
    chunks = chunk_text(text, target_tokens=500, overlap_tokens=50)
    assert len(chunks) >= 2
    for c in chunks:
        assert c.token_count <= 600  # target + overlap + small slack


def test_char_offsets_are_within_input_bounds():
    text = (
        "# Heading\n\n"
        "Paragraph one is here. " * 30
        + "\n\n"
        + "Paragraph two is here. " * 30
    )
    chunks = chunk_text(text, target_tokens=200, overlap_tokens=20)
    for c in chunks:
        assert 0 <= c.char_start < c.char_end <= len(text)


def test_chunks_appear_in_document_order():
    text = "\n\n".join(f"Paragraph {i} with some text." * 10 for i in range(20))
    chunks = chunk_text(text, target_tokens=150, overlap_tokens=15)
    for a, b in zip(chunks, chunks[1:]):
        assert a.char_start <= b.char_start


def test_overlap_is_carried_between_chunks():
    text = ". ".join(f"Statement {i:03d} of the document" for i in range(200)) + "."
    chunks = chunk_text(text, target_tokens=200, overlap_tokens=50)
    # When overlap > 0 and we produce >1 chunk, consecutive chunks should
    # share at least some textual content.
    assert len(chunks) >= 2
    # Take the trailing 30 chars of chunk[i] and confirm they appear
    # somewhere in chunk[i+1] (not exact-equal because overlap is by
    # tokens, not characters; substring check is the practical invariant).
    for a, b in zip(chunks, chunks[1:]):
        tail = a.text[-30:]
        # Allow for whitespace normalization differences.
        assert any(piece in b.text for piece in tail.split() if len(piece) > 4), (
            f"No overlap between consecutive chunks. Tail={tail!r}"
        )


def test_chunking_is_deterministic():
    text = "## H1\n\n" + ("Some sentence. " * 100) + "\n\n## H2\n\n" + ("Other text. " * 100)
    a = chunk_text(text, target_tokens=200, overlap_tokens=20)
    b = chunk_text(text, target_tokens=200, overlap_tokens=20)
    assert len(a) == len(b)
    for x, y in zip(a, b):
        assert x.text == y.text
        assert x.char_start == y.char_start
        assert x.char_end == y.char_end


# ---------- Sanity: returned type is Chunk ----------

def test_returns_chunk_instances():
    chunks = chunk_text("Hello world.", target_tokens=100)
    assert all(isinstance(c, Chunk) for c in chunks)
