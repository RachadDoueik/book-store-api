"""create_embedding_jobs_table

Revision ID: 8f825799beaa
Revises: df366fdbd203
Create Date: 2026-07-02 13:14:47.191417

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '8f825799beaa'
down_revision: Union[str, Sequence[str], None] = 'df366fdbd203'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        'embedding_jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('book_id', UUID(as_uuid=True), sa.ForeignKey('books.id'), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('processed_at', sa.DateTime(), nullable=True)
    )

def downgrade():
    op.drop_table('embedding_jobs')