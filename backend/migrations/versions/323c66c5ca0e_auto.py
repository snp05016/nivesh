"""No-op schema chain placeholder.

Revision ID: 323c66c5ca0e
Revises: 0dc3e605ea33
Create Date: 2026-06-16 05:52:29.685848
"""

from typing import Sequence, Union


revision: str = "323c66c5ca0e"
down_revision: Union[str, Sequence[str], None] = "0dc3e605ea33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Base revision already creates the current schema."""


def downgrade() -> None:
    """No schema changes to revert."""
