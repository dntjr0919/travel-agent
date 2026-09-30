"""add itinerary status

Revision ID: 06a067f5cd68
Revises: 93d37c0ffb94
Create Date: 2026-09-30 12:41:30.668136

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '06a067f5cd68'
down_revision: Union[str, None] = '93d37c0ffb94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "itinerary_items",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="planned",
        ),
    )


def downgrade() -> None:
    op.drop_column("itinerary_items", "status")
