"""POST /chat"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app.schemas import ChatRequest, ChatResponse

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
def chat(request: Request, body: ChatRequest) -> ChatResponse:
    chat_service = request.app.state.chat_service
    try:
        return chat_service.chat(body.query)
    except Exception as e:
        log.exception("chat failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
