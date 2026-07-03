import json
import logging

from app.schemas.chat import ChatMessage, MessageRole, RetrievalRoute, RouterResult, StructuredFilters
from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """
You are a query router for The Wisdom Vault, a bookshop chatbot.
Classify the user's latest message into one of three retrieval routes.

Routes:
- STRUCTURED_FILTER: The user asks about a specific author name, genre/category name,
  price range, or stock availability.
  Examples: "Do you have books by Dostoevsky?", "Show me sci-fi books under $20",
            "What fantasy books are in stock?", "Books by Gabriel García Márquez"

- SEMANTIC_SEARCH: The user describes a vague theme, mood, or concept without naming specifics.
  Examples: "Something about loss and redemption", "A book like Dune but shorter",
            "Dark philosophical novels", "Feel-good summer reads"

- NO_RETRIEVAL: The user asks for general literary knowledge — plot summaries, author
  biographies, historical context, thematic analysis — not about what this bookshop carries.
  Examples: "Who wrote Crime and Punishment?", "What are the themes of 1984?",
            "Tell me about magical realism", "What won the Booker Prize in 2020?"

Respond ONLY with a valid JSON object — no prose, no markdown, no explanation:
{
  "route": "STRUCTURED_FILTER" | "SEMANTIC_SEARCH" | "NO_RETRIEVAL",
  "filters": {
    "author": string | null,
    "category": string | null,
    "max_price": number | null,
    "in_stock": boolean | null
  },
  "search_query": string | null
}

Rules:
- "filters" is populated only for STRUCTURED_FILTER. Extract the specific author name,
  category name, price limit, or in-stock requirement from the user message.
- "search_query" is the cleaned semantic intent for SEMANTIC_SEARCH (strip filler words, keep essence).
- For NO_RETRIEVAL, all fields except "route" should be null or empty defaults.
- author and category should be the name as mentioned by the user (e.g. "Dostoevsky", "sci-fi").
""".strip()


class QueryRouter:

    def __init__(self, llm: LLMProvider):
        self._llm = llm

    async def route(self, user_message: str) -> RouterResult:
        """
        Classify the user message. Returns a RouterResult with the retrieval
        path + any extracted filters.

        Falls back to SEMANTIC_SEARCH if the LLM call fails or returns bad JSON —
        this is the safest default since it will still attempt to find relevant books.
        """
        try:
            messages = [ChatMessage(role=MessageRole.USER, content=user_message)]
            raw = await self._llm.generate(
                system_prompt=ROUTER_SYSTEM_PROMPT,
                messages=messages,
            )
            data = json.loads(raw)

            return RouterResult(
                route=RetrievalRoute(data["route"]),
                filters=StructuredFilters(**data.get("filters", {})),
                search_query=data.get("search_query"),
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"QueryRouter: bad LLM response ({e}) — defaulting to SEMANTIC_SEARCH")
            return RouterResult(
                route=RetrievalRoute.SEMANTIC_SEARCH,
                search_query=user_message,
            )

        except Exception as e:
            logger.error(f"QueryRouter: LLM call failed ({e}) — defaulting to SEMANTIC_SEARCH")
            return RouterResult(
                route=RetrievalRoute.SEMANTIC_SEARCH,
                search_query=user_message,
            )
