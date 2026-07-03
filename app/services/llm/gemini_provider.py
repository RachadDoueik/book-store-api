import logging
from typing import AsyncGenerator

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.schemas.chat import ChatMessage, MessageRole
from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)

# gemini-2.0-flash-lite: fast, free tier, sufficient for bookshop chat
GENERATION_MODEL = "gemini-2.5-flash-lite"


def _to_gemini_contents(messages: list[ChatMessage]) -> list[types.Content]:
    """Convert our internal ChatMessage list to Gemini's Content format."""
    contents = []
    for msg in messages:
        role = "user" if msg.role == MessageRole.USER else "model"
        contents.append(
            types.Content(role=role, parts=[types.Part(text=msg.content)])
        )
    return contents


class GeminiLLMProvider(LLMProvider):

    def __init__(self):
        settings = get_settings()
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def generate(self, system_prompt: str, messages: list[ChatMessage]) -> str:
        """
        Non-streaming. Used by QueryRouter to get a structured JSON response.
        Temperature is low to keep routing decisions deterministic.
        """
        response = await self._client.aio.models.generate_content(
            model=GENERATION_MODEL,
            contents=_to_gemini_contents(messages),
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=256,
            ),
        )
        return response.text

    async def stream(
        self, system_prompt: str, messages: list[ChatMessage]
    ) -> AsyncGenerator[str, None]:
        """Streaming generation — yields text tokens for SSE."""
        async for chunk in await self._client.aio.models.generate_content_stream(
            model=GENERATION_MODEL,
            contents=_to_gemini_contents(messages),
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
                max_output_tokens=1024,
            ),
        ):
            if chunk.text:
                yield chunk.text