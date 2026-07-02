"""merge conflicting migrations

Revision ID: 673c90666b7e
Revises: 8f825799beaa, e748cb939f6e
Create Date: 2026-07-02 13:40:02.321275

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '673c90666b7e'
down_revision: Union[str, Sequence[str], None] = ('8f825799beaa', 'e748cb939f6e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
