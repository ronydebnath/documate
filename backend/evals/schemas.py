"""Pydantic v2 models for the eval harness.

EvalCase mirrors the dataset.yaml schema. CaseResult and RunReport are the
artifacts written to backend/evals/reports/.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal[
    "factual_lookup",
    "multi_hop",
    "aggregation",
    "negation",
    "out_of_scope",
    "ambiguous",
]
Difficulty = Literal["easy", "medium", "hard"]


class EvalCase(BaseModel):
    id: str
    category: Category
    difficulty: Difficulty
    question: str
    reference_answer: str = ""
    expected_source_ids: list[str] = Field(default_factory=list)
    must_contain: list[str] = Field(default_factory=list)
    must_not_contain: list[str] = Field(default_factory=list)
    notes: str = ""


class JudgeVerdict(BaseModel):
    faithful: int = 0  # 0 or 1
    unsupported_claims: list[str] = Field(default_factory=list)
    reason: str = ""
    parse_error: str | None = None


class CaseResult(BaseModel):
    case_id: str
    category: Category
    question: str

    # Pipeline outputs
    answer: str
    retrieved_chunk_ids: list[str]
    cited_chunk_ids: list[str]

    # Retrieval (None for out_of_scope / ambiguous)
    hit_at_k: int | None = None
    mrr: float | None = None

    # Generation
    faithfulness: int = 0
    judge_reason: str = ""
    judge_parse_error: str | None = None
    citation_precision: float | None = None
    citation_recall: float | None = None
    citation_f1: float | None = None
    must_contain_pass: bool = False
    refusal_correct: bool | None = None  # only meaningful for out_of_scope / ambiguous

    # Latency
    retrieve_ms: int = 0
    generate_ms: int = 0
    judge_ms: int = 0


class CategoryAggregate(BaseModel):
    count: int
    hit_at_k: float | None = None
    mrr: float | None = None
    faithfulness: float
    citation_precision: float | None = None
    citation_recall: float | None = None
    citation_f1: float | None = None
    must_contain_pass_rate: float
    refusal_accuracy: float | None = None


class Aggregates(BaseModel):
    overall: CategoryAggregate
    by_category: dict[str, CategoryAggregate]


class RunReport(BaseModel):
    config_name: str
    started_at: str
    finished_at: str
    case_count: int
    cases: list[CaseResult]
    aggregates: Aggregates
