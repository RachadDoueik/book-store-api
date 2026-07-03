"""add_rag_support

Revision ID: 0c02fbd1691a
Revises: 0006_add_book_category
Create Date: 2026-07-03 05:55:53.301802

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

revision : str = '0c02fbd1691a'
down_revision: str = '0006_add_book_category'

VECTOR_DIM = 768


def upgrade():
    # ── 1. pgvector extension ──────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── 2. New columns on books ────────────────────────────────────────────
    op.execute(f"ALTER TABLE books ADD COLUMN IF NOT EXISTS embedding vector({VECTOR_DIM})")
    op.add_column("books", sa.Column("search_vector", TSVECTOR, nullable=True))

    # ── 3. HNSW index (cosine distance) ───────────────────────────────────
    op.execute("""
        CREATE INDEX IF NOT EXISTS books_embedding_hnsw_idx
        ON books USING hnsw (embedding vector_cosine_ops)
        WITH (ef_construction = 64)
    """)

    # ── 4. GIN index (full-text) ───────────────────────────────────────────
    op.execute("""
        CREATE INDEX IF NOT EXISTS books_search_vector_gin_idx
        ON books USING gin (search_vector)
    """)

    # ── 5. embedding_jobs outbox table ────────────────────────────────────
    op.create_table(
        "embedding_jobs",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "book_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("retries", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("embedding_jobs_status_idx", "embedding_jobs", ["status"])
    op.create_index("embedding_jobs_book_id_idx", "embedding_jobs", ["book_id"])

    # ── 6. Trigger ────────────────────────────────────────────────────────
    # Columns listed here MUST all exist on the books table.
    # Book has: title, description, category_id (no author column — authors
    # are a many-to-many via book_authors; category_id is the FK column).
    op.execute("""
        CREATE OR REPLACE FUNCTION queue_embedding_job()
        RETURNS TRIGGER AS $$
        BEGIN
            INSERT INTO embedding_jobs (book_id, status)
            VALUES (NEW.id, 'pending');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER books_embedding_trigger
        AFTER INSERT OR UPDATE OF title, description, category_id
        ON books
        FOR EACH ROW
        EXECUTE FUNCTION queue_embedding_job();
    """)

    # ── 7. Reconciliation view ─────────────────────────────────────────────
    op.execute("""
        CREATE VIEW books_missing_embeddings AS
        SELECT b.id, b.title
        FROM books b
        LEFT JOIN embedding_jobs ej
            ON ej.book_id = b.id
            AND ej.status IN ('pending', 'processing')
        WHERE b.embedding IS NULL
        AND ej.id IS NULL;
    """)


def downgrade():
    op.execute("DROP VIEW IF EXISTS books_missing_embeddings")
    op.execute("DROP TRIGGER IF EXISTS books_embedding_trigger ON books")
    op.execute("DROP FUNCTION IF EXISTS queue_embedding_job()")
    op.drop_table("embedding_jobs")
    op.execute("DROP INDEX IF EXISTS books_search_vector_gin_idx")
    op.execute("DROP INDEX IF EXISTS books_embedding_hnsw_idx")
    op.drop_column("books", "search_vector")
    op.execute("ALTER TABLE books DROP COLUMN IF EXISTS embedding")