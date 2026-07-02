"""add_pgvector_extension

Revision ID: 44feb22c7189
Revises: 0006_add_book_category
Create Date: 2026-07-02 11:26:06.437355

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '44feb22c7189'
down_revision: Union[str, Sequence[str], None] = '0006_add_book_category'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from alembic import op
import sqlalchemy as sa

def upgrade():
    # The IF NOT EXISTS clause ensures it doesn't fail if already present
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

def downgrade():
    # Optional: Remove the extension if you want to completely rollback
    op.execute("DROP EXTENSION IF EXISTS vector;")
