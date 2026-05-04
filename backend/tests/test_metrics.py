"""Eval metric unit tests. Pure: no API calls, no Chroma."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from evals.judges.claude_judge import ClaudeJudge
from evals.metrics.generation import citation_f1, must_contain_pass
from evals.metrics.refusal import refusal_correct
from evals.metrics.retrieval import (
    expected_slug_set,
    hit_at_k,
    mrr,
    slug_of_chunk_id,
    slug_of_expected,
)


# ---------- slug helpers ----------

def test_slug_of_chunk_id_strips_ordinal():
    assert slug_of_chunk_id("leave-parental-leave::0003") == "leave-parental-leave"


def test_slug_of_chunk_id_no_ordinal_returns_input():
    assert slug_of_chunk_id("leave-parental-leave") == "leave-parental-leave"


def test_slug_of_expected_strips_namespace():
    assert slug_of_expected("fairwork/leave-parental-leave") == "leave-parental-leave"


def test_slug_of_expected_passes_through_when_no_namespace():
    assert slug_of_expected("leave-parental-leave") == "leave-parental-leave"


def test_expected_slug_set_strips_all():
    out = expected_slug_set(["fairwork/a", "b", "fairwork/c"])
    assert out == {"a", "b", "c"}


# ---------- hit@k ----------

def test_hit_at_k_match_position_3():
    retrieved = ["foo::0000", "bar::0000", "leave-parental-leave::0003", "baz::0000"]
    expected = ["fairwork/leave-parental-leave"]
    assert hit_at_k(retrieved, expected) == 1


def test_hit_at_k_no_match():
    retrieved = ["foo::0000", "bar::0000", "baz::0001"]
    expected = ["fairwork/leave-parental-leave"]
    assert hit_at_k(retrieved, expected) == 0


def test_hit_at_k_partial_overlap_when_one_of_two_matches():
    retrieved = ["leave-annual-leave::0000", "other::0000"]
    expected = ["fairwork/leave-annual-leave", "fairwork/leave-parental-leave"]
    assert hit_at_k(retrieved, expected) == 1


def test_hit_at_k_empty_expected_returns_zero():
    assert hit_at_k(["x::0000"], []) == 0


# ---------- MRR ----------

def test_mrr_first_position_is_one():
    assert mrr(["leave-parental-leave::0001", "x::0000"], ["fairwork/leave-parental-leave"]) == 1.0


def test_mrr_third_position_is_one_third():
    retrieved = ["x::0000", "y::0000", "leave-parental-leave::0003", "z::0000"]
    expected = ["fairwork/leave-parental-leave"]
    assert mrr(retrieved, expected) == pytest.approx(1.0 / 3.0)


def test_mrr_no_match_returns_zero():
    assert mrr(["x::0000", "y::0000"], ["fairwork/z"]) == 0.0


def test_mrr_empty_expected_returns_zero():
    assert mrr(["x::0000"], []) == 0.0


# ---------- slug-prefix matching across both helpers ----------

def test_chunk_id_matches_namespaced_expected():
    """Documented invariant from the build plan."""
    retrieved = ["notice-and-final-pay::0003"]
    expected = ["fairwork/notice-and-final-pay"]
    assert hit_at_k(retrieved, expected) == 1
    assert mrr(retrieved, expected) == 1.0


# ---------- citation F1 ----------

def test_citation_f1_perfect_overlap():
    p, r, f1 = citation_f1(["a::0000", "b::0001"], ["fairwork/a", "fairwork/b"])
    assert (p, r, f1) == (1.0, 1.0, 1.0)


def test_citation_f1_no_cited_with_expected_is_zero():
    p, r, f1 = citation_f1([], ["fairwork/a"])
    assert (p, r, f1) == (0.0, 0.0, 0.0)


def test_citation_f1_no_cited_no_expected_is_one():
    """No expectation, no citation = vacuous pass."""
    p, r, f1 = citation_f1([], [])
    assert (p, r, f1) == (1.0, 1.0, 1.0)


def test_citation_f1_half_overlap():
    # cited {a}, expected {a, b}: precision=1, recall=0.5, f1≈0.667
    p, r, f1 = citation_f1(["a::0000"], ["fairwork/a", "fairwork/b"])
    assert p == 1.0
    assert r == 0.5
    assert f1 == pytest.approx(2 / 3)


def test_citation_f1_dedups_cited_slugs():
    # Two chunks from the same doc: still 1 unique slug.
    p, r, f1 = citation_f1(["a::0000", "a::0001"], ["fairwork/a"])
    assert (p, r, f1) == (1.0, 1.0, 1.0)


# ---------- must_contain_pass ----------

def test_must_contain_all_present_passes():
    assert must_contain_pass("Notice is 1 week or 4 weeks.", ["1 week", "4 weeks"], []) is True


def test_must_contain_missing_required_fails():
    assert must_contain_pass("Notice is 1 week.", ["1 week", "4 weeks"], []) is False


def test_must_contain_forbidden_present_fails():
    assert must_contain_pass("It depends.", [], ["depends"]) is False


def test_must_contain_case_insensitive():
    assert must_contain_pass("ONE WEEK is the minimum.", ["one week"], []) is True


def test_must_contain_empty_lists_pass():
    assert must_contain_pass("Anything.", [], []) is True


# ---------- refusal_correct ----------

REFUSAL = "I don't have information on that in the Fair Work documents I have access to."


def test_refusal_correct_when_oos_contains_phrase():
    answer = REFUSAL + " Try the ATO instead."
    assert refusal_correct("out_of_scope", answer) is True


def test_refusal_wrong_when_oos_missing_phrase():
    answer = "GST is 10% in Australia."
    assert refusal_correct("out_of_scope", answer) is False


def test_refusal_correct_for_ambiguous_with_clarifier():
    assert refusal_correct(
        "ambiguous", "Could you clarify which type of leave you mean?"
    ) is True


def test_refusal_wrong_for_ambiguous_without_clarifier():
    assert refusal_correct("ambiguous", "Yes, you can take leave.") is False


def test_refusal_returns_none_for_factual_lookup():
    assert refusal_correct("factual_lookup", "Anything goes.") is None


# ---------- judge parse-failure path ----------

class _Block:
    def __init__(self, type_, name=None, input_=None, text=None):
        self.type = type_
        self.name = name
        self.input = input_
        self.text = text


def _make_response(blocks):
    r = MagicMock()
    r.content = blocks
    return r


@patch("evals.judges.claude_judge.anthropic.Anthropic")
def test_judge_returns_zero_on_no_tool_use(mock_anth):
    """Response with no tool_use block -> faithful=0 with parse_error."""
    client = MagicMock()
    client.messages.create.return_value = _make_response([_Block("text", text="hi")])
    mock_anth.return_value = client

    judge = ClaudeJudge(api_key="sk-ant-test")
    verdict = judge.judge("q", "a", [])

    assert verdict.faithful == 0
    assert verdict.parse_error is not None


@patch("evals.judges.claude_judge.anthropic.Anthropic")
def test_judge_returns_zero_on_api_exception(mock_anth):
    client = MagicMock()
    client.messages.create.side_effect = RuntimeError("network down")
    mock_anth.return_value = client

    judge = ClaudeJudge(api_key="sk-ant-test")
    verdict = judge.judge("q", "a", [])

    assert verdict.faithful == 0
    assert verdict.parse_error is not None
    assert "network down" in verdict.parse_error


@patch("evals.judges.claude_judge.anthropic.Anthropic")
def test_judge_returns_one_on_clean_tool_use(mock_anth):
    client = MagicMock()
    client.messages.create.return_value = _make_response([
        _Block(
            "tool_use",
            name="record_faithfulness",
            input_={"faithful": 1, "unsupported_claims": [], "reason": "ok"},
        ),
    ])
    mock_anth.return_value = client

    judge = ClaudeJudge(api_key="sk-ant-test")
    verdict = judge.judge("q", "a", [])

    assert verdict.faithful == 1
    assert verdict.parse_error is None
    assert verdict.reason == "ok"


@patch("evals.judges.claude_judge.anthropic.Anthropic")
def test_judge_forces_zero_when_unsupported_claims_present(mock_anth):
    """Even if model says faithful=1, presence of unsupported_claims forces 0."""
    client = MagicMock()
    client.messages.create.return_value = _make_response([
        _Block(
            "tool_use",
            name="record_faithfulness",
            input_={"faithful": 1, "unsupported_claims": ["claim X"], "reason": "mostly"},
        ),
    ])
    mock_anth.return_value = client

    judge = ClaudeJudge(api_key="sk-ant-test")
    verdict = judge.judge("q", "a", [])

    assert verdict.faithful == 0
    assert verdict.unsupported_claims == ["claim X"]
