"""Citation parser tests. Pure regex; no Anthropic API calls."""

from __future__ import annotations

from app.services.generator import parse_citations


# ---------- Empty / no citations ----------

def test_empty_string_yields_no_citations():
    assert parse_citations("") == []


def test_none_safe_returns_no_citations():
    assert parse_citations(None) == []  # type: ignore[arg-type]


def test_text_without_citations_yields_empty():
    assert parse_citations("Some prose with no chunk IDs at all.") == []


# ---------- Single + multiple distinct ----------

def test_single_citation_extracted():
    text = "Yes, two weeks notice [ending-employment-resignation::0001]."
    assert parse_citations(text) == ["ending-employment-resignation::0001"]


def test_multiple_distinct_citations_in_order():
    text = "First point [doc-a::0001] and second point [doc-b::0042]."
    assert parse_citations(text) == ["doc-a::0001", "doc-b::0042"]


# ---------- Dedup ----------

def test_duplicate_citations_collapsed_first_occurrence_wins():
    text = "[x::0001] then again [x::0001] and once more [x::0001]."
    assert parse_citations(text) == ["x::0001"]


def test_interleaved_duplicates_keep_first_occurrence_order():
    text = "[b::0001] then [a::0002] then [b::0001] again."
    assert parse_citations(text) == ["b::0001", "a::0002"]


# ---------- Invalid forms ignored ----------

def test_non_citation_brackets_ignored():
    assert parse_citations("[just some text]") == []


def test_missing_double_colon_ignored():
    assert parse_citations("[doc-a 0001]") == []


def test_non_numeric_ordinal_ignored():
    assert parse_citations("[doc-a::abcd]") == []


def test_wrong_ordinal_width_ignored():
    # The ingest pipeline always emits exactly 4-digit ordinals.
    assert parse_citations("[doc-a::1]") == []
    assert parse_citations("[doc-a::99999]") == []


def test_empty_slug_ignored():
    assert parse_citations("[::0001]") == []


def test_empty_ordinal_ignored():
    assert parse_citations("[doc-a::]") == []


def test_uppercase_slug_ignored():
    # Slugs are lowercased by the ingest pipeline.
    assert parse_citations("[Doc-A::0001]") == []


# ---------- Surrounding punctuation / markdown ----------

def test_citation_adjacent_to_period():
    assert parse_citations("Yes [x::0001].") == ["x::0001"]


def test_citation_adjacent_to_comma():
    assert parse_citations("Yes [x::0001], also note...") == ["x::0001"]


def test_citation_inside_markdown_emphasis():
    assert parse_citations("**[x::0001]**") == ["x::0001"]


def test_multiple_citations_adjacent():
    text = "Both apply [a::0001][b::0002]."
    assert parse_citations(text) == ["a::0001", "b::0002"]


# ---------- Realistic chunk IDs ----------

def test_realistic_chunk_id_from_corpus():
    text = (
        "Casual employees do not have to give notice when resigning "
        "[ending-employment-resignation::0001]."
    )
    assert parse_citations(text) == ["ending-employment-resignation::0001"]


def test_smallbusiness_prefix_chunk_id():
    text = "See the small business guide [sb-ending-employment::0002]."
    assert parse_citations(text) == ["sb-ending-employment::0002"]
