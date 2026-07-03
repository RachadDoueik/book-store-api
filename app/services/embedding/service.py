from app.services.embedding.base import EmbeddingProvider
from app.services.embedding.gemini_provider import GeminiEmbeddingProvider


def build_embed_text(
    title: str,
    author_names: list[str],   # resolved from Book.authors many-to-many
    description: str | None,
    category_name: str | None, # resolved from Book.category relationship
) -> str:
    """
    Builds the string we embed for each book.

    We combine structured fields into one coherent string so the model
    captures all semantic dimensions of the book. Author names are joined
    with commas since a book can have multiple authors.

    Example output:
      "Title: Dune | Authors: Frank Herbert | Category: Science Fiction |
       Description: A science fiction masterpiece set on the desert planet Arrakis..."
    """
    parts = [f"Title: {title}"]

    if author_names:
        parts.append(f"Authors: {', '.join(author_names)}")

    if category_name:
        parts.append(f"Category: {category_name}")

    if description:
        # Trim very long descriptions — we only need enough for semantic signal
        parts.append(f"Description: {description[:600]}")

    return " | ".join(parts)


class EmbeddingService:
    """
    Provider-agnostic facade.
    Swap GeminiEmbeddingProvider for any other provider in one place.
    """

    def __init__(self, provider: EmbeddingProvider | None = None):
        self._provider = provider or GeminiEmbeddingProvider()

    async def embed_document(self, text: str) -> list[float]:
        return await self._provider.embed_document(text)

    async def embed_query(self, text: str) -> list[float]:
        return await self._provider.embed_query(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return await self._provider.embed_batch(texts)

    @property
    def dimensions(self) -> int:
        return self._provider.dimensions