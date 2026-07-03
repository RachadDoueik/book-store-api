import logging

from app.models.author import Author
from app.models.book import Book
from app.models.category import Category
from app.schemas.chat import BookContext, RetrievalRoute, StructuredFilters
from sqlalchemy import and_, func, select, literal_column
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

TOP_K = 5
MAX_DESCRIPTION_PREVIEW = 300


def _book_to_context(
    book: Book,
    route: RetrievalRoute,
    score: float | None = None,
) -> BookContext:
    """
    Map a Book ORM object (with authors + category already loaded) to BookContext.

    Book.authors is a many-to-many list → we resolve to a list of name strings.
    Book.category is a nullable relationship → we resolve to the category name string.
    """
    return BookContext(
        id=str(book.id),
        title=book.title,
        page_count=book.page_count,
        authors=[a.name for a in book.authors],  # list from many-to-many
        description=book.description,
        category=book.category.name if book.category else None,
        price=float(book.price) if book.price is not None else None,
        in_stock=book.stock > 0,
        isbn=book.isbn,
        release_date=str(book.release_date) if book.release_date else None,
        source=route,
        score=score,
    )


def _base_select():
    """
    All retrieval queries must eagerly load authors and category so that
    _book_to_context can resolve the relationship values without extra queries.
    """
    return select(Book).options(
        selectinload(Book.authors),
        selectinload(Book.category),
    )


class HybridSearchService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def filter_query(self, filters: StructuredFilters) -> list[BookContext]:
        """
        Pure SQL structured filtering — fastest path for explicit catalog queries.
        Examples: "books by Dostoevsky", "sci-fi under $20", "what's in stock"

        Author filtering uses Book.authors.any() which generates an EXISTS subquery
        against the book_authors association table — no manual join needed.
        Category filtering uses Book.category.has() which generates an EXISTS subquery
        against the categories table.
        """
        conditions = []

        if filters.author:
            # EXISTS (SELECT 1 FROM book_authors ba JOIN authors a ON ... WHERE a.name ILIKE ...)
            conditions.append(
                Book.authors.any(Author.name.ilike(f"%{filters.author}%"))
            )

        if filters.category:
            # EXISTS (SELECT 1 FROM categories c WHERE c.id = book.category_id AND c.name ILIKE ...)
            conditions.append(
                Book.category.has(Category.name.ilike(f"%{filters.category}%"))
            )

        if filters.max_price is not None:
            conditions.append(Book.price <= filters.max_price)

        if filters.in_stock:
            conditions.append(Book.stock > 0)

        stmt = _base_select().limit(TOP_K)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        result = await self._db.execute(stmt)
        books = result.scalars().all()
        return [_book_to_context(b, RetrievalRoute.STRUCTURED_FILTER) for b in books]

    async def semantic_search(
        self,
        query_embedding: list[float],
        filters: StructuredFilters | None = None,
    ) -> list[BookContext]:
        """
        HNSW cosine-distance vector search with optional pre-filters.
        The <=> operator is pgvector's cosine distance — lower = more similar.
        We convert to a similarity score (1 - distance) for display.

        Pre-filters narrow the vector search to a subset of books before
        ranking by embedding distance. This is more accurate than post-filtering.
        """
        vec_literal = f"[{','.join(str(v) for v in query_embedding)}]"

        conditions = [Book.embedding.isnot(None)]

        if filters:
            if filters.author:
                conditions.append(
                    Book.authors.any(Author.name.ilike(f"%{filters.author}%"))
                )
            if filters.category:
                conditions.append(
                    Book.category.has(Category.name.ilike(f"%{filters.category}%"))
                )
            if filters.max_price is not None:
                conditions.append(Book.price <= filters.max_price)
            if filters.in_stock:
                conditions.append(Book.stock > 0)

        distance_expr = literal_column(f"embedding <=> '{vec_literal}'::vector")

        stmt = (
            _base_select()
            .add_columns(distance_expr.label("distance"))
            .where(and_(*conditions))
            .order_by(distance_expr)
            .limit(TOP_K)
        )

        result = await self._db.execute(stmt)
        rows = result.all()

        return [
            _book_to_context(
                row.Book,
                RetrievalRoute.SEMANTIC_SEARCH,
                score=round(1 - row.distance, 4),
            )
            for row in rows
        ]

    async def full_text_search(self, query: str) -> list[BookContext]:
        """
        GIN-indexed tsvector keyword search on the pre-computed search_vector column.
        Covers title + author names + description + category name.
        Used as a fallback when semantic search returns nothing.
        """
        ts_query = func.plainto_tsquery("english", query)

        stmt = (
            _base_select()
            .where(Book.search_vector.op("@@")(ts_query))
            .order_by(func.ts_rank(Book.search_vector, ts_query).desc())
            .limit(TOP_K)
        )

        result = await self._db.execute(stmt)
        books = result.scalars().all()
        return [_book_to_context(b, RetrievalRoute.SEMANTIC_SEARCH) for b in books]