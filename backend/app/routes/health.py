"""GET /health"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.config import get_settings
from app.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    s = get_settings()
    store = request.app.state.store
    return HealthResponse(
        status="ok",
        collection_size=store.count(),
        generator_model=s.anthropic_generator_model,
        embedding_model=s.embedding_model,
    )
