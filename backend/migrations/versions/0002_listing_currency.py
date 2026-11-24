"""Each listing has a currency (USD unless the seller chooses another).

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False))
    op.create_check_constraint(op.f("ck_listings_currency"), "listings", "currency IN ('USD', 'EUR', 'GBP', 'KZT')")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_listings_currency"), "listings", type_="check")
    op.drop_column("listings", "currency")
