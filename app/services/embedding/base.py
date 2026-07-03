from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):

    @abstractmethod
    async def embed_document(self, text: str) -> list[float]:
        """Embed text at write-time (indexing a book). Uses RETRIEVAL_DOCUMENT task."""
        ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Embed text at query-time (user question). Uses RETRIEVAL_QUERY task."""
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple document texts concurrently."""
        ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        ...