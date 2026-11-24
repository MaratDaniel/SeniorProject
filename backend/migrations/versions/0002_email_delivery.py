"""Track delivery of account email through Resend."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    op.add_column("email_outbox", sa.Column("template", sa.String(64)))
    op.add_column("email_outbox", sa.Column("template_link", sa.Text()))
    op.add_column("email_outbox", sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.add_column("email_outbox", sa.Column("delivery_key", sa.String(32)))
    op.add_column("email_outbox", sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
    op.add_column("email_outbox", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("email_outbox", sa.Column("failed_at", sa.DateTime(timezone=True)))
    op.add_column("email_outbox", sa.Column("provider_id", sa.String(64)))
    op.create_unique_constraint("uq_email_outbox_delivery_key", "email_outbox", ["delivery_key"])
    op.create_index(
        "ix_email_outbox_pending_delivery",
        "email_outbox",
        ["next_attempt_at", "id"],
        postgresql_where=sa.text("delivery_key IS NOT NULL AND sent_at IS NULL AND failed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_email_outbox_pending_delivery", table_name="email_outbox")
    op.drop_constraint("uq_email_outbox_delivery_key", "email_outbox", type_="unique")
    for column in ("provider_id", "failed_at", "attempts", "next_attempt_at", "delivery_key", "expires_at", "template_link", "template"):
        op.drop_column("email_outbox", column)
