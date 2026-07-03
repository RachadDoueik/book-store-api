import asyncio
import logging
from functools import partial

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.services.embedding.base import EmbeddingProvider

logger = logging.getLogger(__name__)

DIMENSIONS = 768
MODEL = "gemini-embedding-001"

# Max concurrent embed calls — stays well within Gemini free tier rate limits
_SEMAPHORE = asyncio.Semaphore(5)


class GeminiEmbeddingProvider(EmbeddingProvider):
    """
    Wraps gemini-embedding-001 (768 dims via MRL).
    The SDK's embed_content is synchronous so we dispatch to a thread pool
    to avoid blocking the FastAPI event loop.
    """

    def __init__(self):
        settings = get_settings()
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    @property
    def dimensions(self) -> int:
        return DIMENSIONS

    def _call_api(self, text: str, task_type: str) -> list[float]:
        result = self._client.models.embed_content(
            model=MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=DIMENSIONS,
            ),
        )
        return result.embeddings[0].values

    async def _embed(self, text: str, task_type: str) -> list[float]:
        text = text.replace("\n", " ").strip()
        loop = asyncio.get_event_loop()
        async with _SEMAPHORE:
            return await loop.run_in_executor(
                None, partial(self._call_api, text, task_type)
            )

    async def embed_document(self, text: str) -> list[float]:
        return await self._embed(text, "RETRIEVAL_DOCUMENT")

    async def embed_query(self, text: str) -> list[float]:
        """
        RETRIEVAL_QUERY produces a different embedding optimised for matching
        against RETRIEVAL_DOCUMENT vectors — this improves recall at query time.
        """
        return await self._embed(text, "RETRIEVAL_QUERY")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return list(
            await asyncio.gather(*[self.embed_document(t) for t in texts])
        )
