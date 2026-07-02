"""add_update_tsvector_trigger

Revision ID: e748cb939f6e
Revises: df366fdbd203
Create Date: 2026-07-02 13:14:47.191417

"""

from alembic import op
from typing import Sequence, Union

revision: str = 'e748cb939f6e'
down_revision: Union[str, Sequence[str], None] = 'df366fdbd203'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():

    #Create Trigger to keep search_vector in sync
    op.execute("""
        CREATE TRIGGER tsvectorupdate BEFORE INSERT OR UPDATE
        ON books FOR EACH ROW EXECUTE FUNCTION
        tsvector_update_trigger(tsvector, 'pg_catalog.english', title, description);
    """)

def downgrade():
    # Drop trigger first
    op.execute("DROP TRIGGER IF EXISTS tsvectorupdate ON books")