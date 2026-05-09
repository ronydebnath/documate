"""POST /chat"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings
from app.schemas import ChatRequest, ChatResponse

router = APIRouter()
log = logging.getLogger(__name__)

# Limiter is module-scoped because slowapi reads the limit string at decorator
# time. The Limiter instance attached to app.state in main.py is the one
# slowapi's middleware actually uses; this one just provides the @limit
# decorator. Both share the same key_func so per-IP keys are consistent.
_settings = get_settings()
_limiter = Limiter(key_func=get_remote_address)


def _check_demo_key(request: Request) -> None:
    expected = request.app.state.demo_key
    if not expected:
        return
    provided = request.query_params.get("key") or request.headers.get("x-demo-key")
    if provided != expected:
        raise HTTPException(status_code=401, detail="Missing or invalid demo key")


@router.post("/chat", response_model=ChatResponse)
@_limiter.limit(_settings.chat_rate_limit)
def chat(request: Request, body: ChatRequest) -> ChatResponse:
    _check_demo_key(request)
    chat_service = request.app.state.chat_service
    try:
        return chat_service.chat(body.query)
    except Exception as e:
        log.exception("chat failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
