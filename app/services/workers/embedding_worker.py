"""
Embedding worker — processes pending embedding_jobs rows.

Started automatically from the FastAPI lifespan (see main.py patch).
Runs as a long-lived background asyncio task on the same process.
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.book import Book
from app.models.embedding_job import EmbeddingJob
from app.services.embedding.service import EmbeddingService, build_embed_text

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
POLL_INTERVAL_SECONDS = 10
BATCH_SIZE = 20


async def _process_batch(db: AsyncSession, embedding_service: EmbeddingService) -> int:
    """
    Claim and process one batch of pending jobs.

    WITH FOR UPDATE SKIP LOCKED is production-safe for concurrent workers:
    each instance locks the rows it's processing and skips rows already
    locked by another worker instance.
    """
    result = await db.execute(
        select(EmbeddingJob)
        .where(EmbeddingJob.status == "pending")
        .where(EmbeddingJob.retries < MAX_RETRIES)
        .order_by(EmbeddingJob.created_at)
        .limit(BATCH_SIZE)
        .with_for_update(skip_locked=True)
    )
    jobs = result.scalars().all()
    if not jobs:
        return 0

    for job in jobs:
        try:
            job.status = "processing"
            await db.flush()

            # Load the book with both relationships we need:
            # - Book.authors  → many-to-many, needed for author names in embed text + tsvector
            # - Book.category → many-to-one, needed for category name in embed text + tsvector
            book_result = await db.execute(
                select(Book)
                .options(
                    selectinload(Book.authors),
                    selectinload(Book.category),
                )
                .where(Book.id == job.book_id)
            )
            book = book_result.scalar_one_or_none()

            if book is None:
                job.status = "failed"
                job.error = "Book not found — may have been deleted"
                logger.warning(f"Job {job.id}: book {job.book_id} not found")
                continue

            # Resolve relationship values
            author_names = [a.name for a in book.authors]
            category_name = book.category.name if book.category else None

            # Build the text we embed
            embed_text = build_embed_text(
                title=book.title,
                author_names=author_names,
                description=book.description,
                category_name=category_name,
            )

            # Generate embedding
            embedding = await embedding_service.embed_document(embed_text)

            # Build tsvector input string — includes all searchable text fields.
            # Author names and category name come from loaded relationships.
            ts_input = " ".join(filter(None, [
                book.title,
                " ".join(author_names),
                category_name or "",
                book.description or "",
            ]))

            # Write embedding + tsvector atomically in one UPDATE
            await db.execute(
                text("""
                    UPDATE books
                    SET
                        embedding     = CAST(:embedding AS vector),
                        search_vector = to_tsvector('english', :ts_input)
                    WHERE id = :book_id
                """),
                {
                    "embedding": f"[{','.join(str(v) for v in embedding)}]",
                    "ts_input": ts_input,
                    "book_id": str(book.id),
                },
            )

            job.status = "done"
            job.processed_at = datetime.now(timezone.utc)
            logger.info(
                f"Embedded '{book.title}' "
                f"(authors: {author_names}, category: {category_name})"
            )

        except Exception as e:
            job.retries += 1
            job.error = str(e)[:500]
            job.status = "pending" if job.retries < MAX_RETRIES else "failed"
            logger.error(
                f"Job {job.id} failed (attempt {job.retries}/{MAX_RETRIES}): {e}",
                exc_info=True,
            )

    await db.commit()
    return len(jobs)


async def reconcile_missing(db: AsyncSession) -> int:
    """
    Safety net — finds books with no embedding and no pending job and queues them.
    Run once on worker startup and optionally as a daily task.
    """
    result = await db.execute(
        text("""
            SELECT b.id
            FROM books b
            LEFT JOIN embedding_jobs ej
                ON ej.book_id = b.id
                AND ej.status IN ('pending', 'processing')
            WHERE b.embedding IS NULL
            AND ej.id IS NULL
        """)
    )
    missing_ids = result.scalars().all()

    if not missing_ids:
        logger.info("Reconciliation: no missing embeddings")
        return 0

    logger.warning(f"Reconciliation: queuing {len(missing_ids)} books with missing embeddings")
    for book_id in missing_ids:
        db.add(EmbeddingJob(book_id=book_id))

    await db.commit()
    return len(missing_ids)


async def run_worker(db: AsyncSession, embedding_service: EmbeddingService) -> None:
    """
    Long-running poll loop. Called from FastAPI lifespan as an asyncio task.
    """
    logger.info("Embedding worker started")
    await reconcile_missing(db)

    while True:
        try:
            processed = await _process_batch(db, embedding_service)
            if processed:
                logger.info(f"Worker: processed {processed} jobs")
        except Exception as e:
            logger.error(f"Worker poll error: {e}", exc_info=True)

        await asyncio.sleep(POLL_INTERVAL_SECONDS)