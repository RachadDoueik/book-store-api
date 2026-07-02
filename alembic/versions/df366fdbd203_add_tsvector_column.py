"""add_tsvector_column

Revision ID: df366fdbd203
Revises: 44feb22c7189
Create Date: 2026-07-02 12:17:48.438595

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import TSVECTOR


# revision identifiers, used by Alembic.
revision: str = 'df366fdbd203'
down_revision: Union[str, Sequence[str], None] = '44feb22c7189'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 1. Add vector column for embeddings
    op.add_column('books', sa.Column('embedding', Vector(1536), nullable=True))
    
    # 2. Add tsvector column for FTS
    op.add_column('books', sa.Column('tsvector', TSVECTOR))
    
    # 3. Create Indexes
    op.create_index('ix_books_search_vector', 'books', ['tsvector'], postgresql_using='gin')
    op.execute("CREATE INDEX ON books USING hnsw (embedding vector_cosine_ops)")

def downgrade():
    op.drop_index('ix_books_search_vector', table_name='books')
    op.drop_column('books', 'tsvector')
    op.drop_column('books', 'embedding')