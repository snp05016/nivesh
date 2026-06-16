"""initial_schema

Revision ID: 0dc3e605ea33
Revises: 
Create Date: 2026-06-16 05:40:37.823639

"""
from typing import Sequence, Union

from alembic import op
from models.db_models import Base


# revision identifiers, used by Alembic.
revision: str = '0dc3e605ea33'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    """Downgrade schema."""
    Base.metadata.drop_all(op.get_bind())
