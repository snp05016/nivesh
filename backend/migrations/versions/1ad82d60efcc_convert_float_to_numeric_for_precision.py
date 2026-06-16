"""No-op schema chain placeholder.

Revision ID: 1ad82d60efcc
Revises: 323c66c5ca0e
Create Date: 2026-06-16 05:58:30.657231
"""

from typing import Sequence, Union


revision: str = "1ad82d60efcc"
down_revision: Union[str, Sequence[str], None] = "323c66c5ca0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Base revision already creates the current schema."""


def downgrade() -> None:
    """No schema changes to revert."""
