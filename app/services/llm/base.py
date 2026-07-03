from abc import ABC, abstractmethod
from typing import AsyncGenerator

from app.schemas.chat import ChatMessage


class LLMProvider(ABC):

    @abstractmethod
    async def generate(self, system_prompt: str, messages: list[ChatMessage]) -> str:
        """
        Non-streaming generation.
        Used by the query router which needs a complete JSON response before proceeding.
        """
        ...

    @abstractmethod
    async def stream(
        self, system_prompt: str, messages: list[ChatMessage]
    ) -> AsyncGenerator[str, None]:
        """
        Streaming generation. Yields string tokens as they arrive from the model.
        Used by the chat endpoint for SSE responses.
        """
        ...