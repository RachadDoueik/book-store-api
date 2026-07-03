import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.chat import BookContext, ChatMessage, RouterResult
from app.services.chat.prompt_builder import PromptBuilder
from app.services.chat.query_router import QueryRouter
from app.services.embedding.service import EmbeddingService
from app.services.llm.base import LLMProvider
from app.services.retrieval.service import RetrievalService

logger = logging.getLogger(__name__)


class ChatService:
    """
    Orchestrates the full RAG pipeline per request:

      1. QueryRouter    → classify intent, extract filters
      2. RetrievalService → fetch relevant books from Postgres
      3. PromptBuilder  → assemble system prompt + context + history
      4. LLMProvider    → stream the generated response

    Instantiated per-request (not a singleton) because it holds a db session.
    """

    def __init__(
        self,
        db: AsyncSession,
        llm: LLMProvider,
        embedding_service: EmbeddingService,
    ):
        self._router = QueryRouter(llm)
        self._retrieval = RetrievalService(db, embedding_service)
        self._prompt_builder = PromptBuilder()
        self._llm = llm

    async def stream_response(
        self,
        user_message: str,
        conversation_history: list[ChatMessage],
    ) -> AsyncGenerator[dict, None]:
        """
        Full pipeline. Yields dicts for SSE serialization:

          {"type": "metadata", "route": "...", "books": [...]}   ← sent first, once
          {"type": "token",    "content": "..."}                  ← one per token
          {"type": "done"}                                         ← sent last
          {"type": "error",   "message": "..."}                   ← only on failure
        """
        # ── Step 1: Route ────────────────────────────────────────────────────
        router_result: RouterResult = await self._router.route(user_message)
        logger.info(f"route={router_result.route.value} filters={router_result.filters}")

        # ── Step 2: Retrieve ─────────────────────────────────────────────────
        retrieved_books: list[BookContext] = await self._retrieval.retrieve(
            user_message, router_result
        )

        # ── Step 3: Emit metadata ────────────────────────────────────────────
        # The frontend can use this to render "Searching catalog..." spinners
        # and to show source citations alongside the streamed answer.
        yield {
            "type": "metadata",
            "route": router_result.route.value,
            "books": [b.model_dump() for b in retrieved_books],
        }

        # ── Step 4: Assemble prompt ──────────────────────────────────────────
        system_prompt, messages = self._prompt_builder.build(
            user_message=user_message,
            router_result=router_result,
            retrieved_books=retrieved_books,
            conversation_history=conversation_history,
        )

        # ── Step 5: Stream generation ────────────────────────────────────────
        async for token in self._llm.stream(system_prompt, messages):
            yield {"type": "token", "content": token}

        yield {"type": "done"}