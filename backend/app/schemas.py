"""Pydantic v2 schemas for the chat API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    history: list[dict] = Field(
        default_factory=list,
        description="Reserved for multi-turn; ignored in v1.",
    )


class Citation(BaseModel):
    chunk_id: str
    source_url: str
    title: str
    snippet: str


class LatencyInfo(BaseModel):
    retrieve: int
    generate: int
    total: int


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    retrieved_chunk_ids: list[str]
    latency_ms: LatencyInfo


class HealthResponse(BaseModel):
    status: str
    collection_size: int
    generator_model: str
    embedding_model: str
