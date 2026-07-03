import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.chat import BookContext, RetrievalRoute, RouterResult
from app.services.embedding.service import EmbeddingService
from app.services.retrieval.hybrid_search import HybridSearchService

logger = logging.getLogger(__name__)


class RetrievalService:
    """
    Unified retrieval facade.
    Accepts a RouterResult (from QueryRouter) and returns list[BookContext]
    regardless of which internal path ran.
    """

    def __init__(self, db: AsyncSession, embedding_service: EmbeddingService):
        self._search = HybridSearchService(db)
        self._embedding = embedding_service

    async def retrieve(
        self, query: str, router_result: RouterResult
    ) -> list[BookContext]:
        start = time.monotonic()
        route = router_result.route
        results: list[BookContext] = []

        try:
            if route == RetrievalRoute.NO_RETRIEVAL:
                results = []

            elif route == RetrievalRoute.STRUCTURED_FILTER:
                results = await self._search.filter_query(router_result.filters)

                # Fallback: if structured filters found nothing, try semantic search
                # on the raw user query — the user may have phrased it oddly
                if not results:
                    logger.info("Structured filter returned 0 results — falling back to semantic")
                    results = await self._semantic(query)

            elif route == RetrievalRoute.SEMANTIC_SEARCH:
                search_query = router_result.search_query or query
                results = await self._semantic(search_query, router_result.filters)

                # Fallback: if vector search found nothing, try full-text keyword search
                if not results:
                    logger.info("Semantic search returned 0 results — falling back to full-text")
                    results = await self._search.full_text_search(search_query)

        except Exception as e:
            # Retrieval failure must never kill the chat response.
            # The prompt builder handles empty context gracefully by telling
            # the model no catalog results were found.
            logger.error(f"Retrieval failed [route={route}]: {e}", exc_info=True)
            results = []

        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
        logger.info(
            "retrieval.complete",
            extra={
                "route": route.value,
                "result_count": len(results),
                "latency_ms": elapsed_ms,
                "retrieved_ids": [r.id for r in results],
            },
        )
        return results

    async def _semantic(
        self, query: str, filters=None
    ) -> list[BookContext]:
        query_embedding = await self._embedding.embed_query(query)
        return await self._search.semantic_search(query_embedding, filters)