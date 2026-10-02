"""add itinerary location metadata

Revision ID: b31c9de0b9a2
Revises: 06a067f5cd68
Create Date: 2026-10-02 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b31c9de0b9a2"
down_revision: Union[str, None] = "06a067f5cd68"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("itinerary_items", sa.Column("place_candidate_id", sa.Integer(), nullable=True))
    op.add_column("itinerary_items", sa.Column("place_provider", sa.String(length=30), nullable=True))
    op.add_column("itinerary_items", sa.Column("external_place_id", sa.String(length=255), nullable=True))
    op.add_column("itinerary_items", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("itinerary_items", sa.Column("longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("itinerary_items", "longitude")
    op.drop_column("itinerary_items", "latitude")
    op.drop_column("itinerary_items", "external_place_id")
    op.drop_column("itinerary_items", "place_provider")
    op.drop_column("itinerary_items", "place_candidate_id")
