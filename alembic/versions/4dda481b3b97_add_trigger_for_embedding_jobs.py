"""add_trigger_for_embedding_jobs

Revision ID: 4dda481b3b97
Revises: 673c90666b7e
Create Date: 2026-07-02 13:59:40.701922

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '4dda481b3b97'
down_revision: Union[str, Sequence[str], None] = '673c90666b7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 1. Create the trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION trigger_insert_embedding_job()
        RETURNS TRIGGER AS $$
        BEGIN
            INSERT INTO embedding_jobs (book_id, status)
            VALUES (NEW.id, 'pending')
            ON CONFLICT (book_id) DO UPDATE SET status = 'pending';
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 2. Create the trigger to execute on INSERT or UPDATE
    op.execute("""
        CREATE TRIGGER trg_books_embedding_update
        AFTER INSERT OR UPDATE OF title, description ON books
        FOR EACH ROW EXECUTE FUNCTION trigger_insert_embedding_job();
    """)

def downgrade():
    # Drop in reverse order
    op.execute("DROP TRIGGER IF EXISTS trg_books_embedding_update ON books")
    op.execute("DROP FUNCTION IF EXISTS trigger_insert_embedding_job")