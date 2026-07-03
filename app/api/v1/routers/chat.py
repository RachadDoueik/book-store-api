"""
Chat endpoint with SSE streaming.
Fits into the existing router structure — include this in app/api/v1/router.py.
"""
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.limiter import limiter
from app.schemas.chat import ChatRequest
from app.services.chat.service import ChatService
from app.services.embedding.service import EmbeddingService
from app.services.llm.gemini_provider import GeminiLLMProvider

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)


def _get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    """
    Build the ChatService for this request.
    Uses your existing get_db dependency — same pattern as BookService, CartService, etc.
    LLM and EmbeddingService are stateless so we build them fresh per request.
    """
    llm = GeminiLLMProvider()
    embedding_service = EmbeddingService()
    return ChatService(db=db, llm=llm, embedding_service=embedding_service)


async def _sse_generator(
    chat_service: ChatService,
    request: ChatRequest,
) -> AsyncGenerator[str, None]:
    """
    Converts the ChatService async generator into SSE wire format.

    Each event:  data: <json string>\n\n

    Event types:
      {"type": "metadata", "route": "...", "books": [...]}   ← sent first, once
      {"type": "token",    "content": "..."}                 ← one per streamed token
      {"type": "error",    "message": "..."}                 ← only on failure
      {"type": "done"}                                        ← always sent last
    """
    try:
        async for event in chat_service.stream_response(
            user_message=request.message,
            conversation_history=request.conversation_history,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    except Exception as e:
        logger.error(f"SSE stream error: {e}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'message': 'Something went wrong. Please try again.'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"


@router.post("")
@limiter.limit("20/minute")   # reuses your existing SlowAPI limiter + Redis
async def chat(
    request: Request,          # required by SlowAPI for rate-limit key extraction
    body: ChatRequest,
    chat_service: ChatService = Depends(_get_chat_service),
) -> StreamingResponse:
    """
    SSE streaming chat endpoint.

    POST /api/v1/chat
    Body: { "message": "...", "conversation_history": [...] }

    The response is a stream of Server-Sent Events. Each event is a JSON object.
    The client should consume this with EventSource or a fetch-based SSE reader.

    Headers set:
      Cache-Control: no-cache        — prevents buffering by intermediate proxies
      X-Accel-Buffering: no          — disables nginx proxy buffering specifically
      Connection: keep-alive         — keeps the TCP connection open for streaming
    """
    return StreamingResponse(
        _sse_generator(chat_service, body),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )