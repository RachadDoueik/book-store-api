"""
One-off backfill — queues embedding jobs for all existing books that
have no embedding and no pending job already queued.

Run once after applying the migration:
    python scripts/backfill_embeddings.py

The worker (started via FastAPI lifespan) picks up and processes the jobs.
"""
import asyncio
import logging

from sqlalchemy import text

from app.core.database import AsyncSessionFactory
from app.models.embedding_job import EmbeddingJob

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def backfill():
    async with AsyncSessionFactory() as db:
        result = await db.execute(
            text("""
                SELECT b.id, b.title
                FROM books b
                LEFT JOIN embedding_jobs ej
                    ON ej.book_id = b.id
                    AND ej.status IN ('pending', 'processing')
                WHERE b.embedding IS NULL
                AND ej.id IS NULL
                ORDER BY b.created_at
            """)
        )
        rows = result.all()

        if not rows:
            logger.info("All books already have embeddings — nothing to backfill.")
            return

        logger.info(f"Queuing {len(rows)} books...")
        for row in rows:
            db.add(EmbeddingJob(book_id=row.id))
            logger.info(f"  Queued: {row.title} ({row.id})")

        await db.commit()
        logger.info(
            f"Done. {len(rows)} jobs queued. "
            "Start the app (lifespan worker) to process them."
        )


if __name__ == "__main__":
    asyncio.run(backfill())
