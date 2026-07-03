from enum import Enum
from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    role: MessageRole
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_history: list[ChatMessage] = Field(default_factory=list)


class RetrievalRoute(str, Enum):
    STRUCTURED_FILTER = "STRUCTURED_FILTER"
    SEMANTIC_SEARCH = "SEMANTIC_SEARCH"
    NO_RETRIEVAL = "NO_RETRIEVAL"


class StructuredFilters(BaseModel):
    # Author name (partial match) — resolved via book_authors JOIN
    author: str | None = None
    # Category name (partial match) — resolved via categories JOIN
    category: str | None = None
    max_price: float | None = None
    in_stock: bool | None = None


class RouterResult(BaseModel):
    route: RetrievalRoute
    filters: StructuredFilters = Field(default_factory=StructuredFilters)
    search_query: str | None = None


class BookContext(BaseModel):
    """
    Uniform representation of a Book returned by any retrieval path.
    Built from the Book ORM object with its relationships already loaded.

    Note: authors is a list because Book has a many-to-many with Author.
    """
    id: str
    title: str
    authors: list[str]          # ["Author One", "Author Two"]
    page_count : int | None
    description: str | None
    category: str | None        # category name resolved from relationship
    price: float | None
    in_stock: bool
    isbn: str | None
    release_date: str | None    # ISO date string e.g. "2021-03-15"
    source: RetrievalRoute
    score: float | None = None  # cosine similarity score (SEMANTIC_SEARCH only)
