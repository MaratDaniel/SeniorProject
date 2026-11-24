"""Track delivery of account email through Resend."""

import sqlalchemy as sa
from alembic import context, op

revision = "0003"
down_revision = "0002"


def upgrade() -> None:
    if not context.is_offline_mode():
        # Both branches used revision 0002 before merging. A database stamped
        # with that revision may have applied only the email migration.
        inspector = sa.inspect(op.get_bind())
        if not any(column["name"] == "currency" for column in inspector.get_columns("listings")):
            op.add_column("listings", sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False))
            op.create_check_constraint(op.f("ck_listings_currency"), "listings", "currency IN ('USD', 'EUR', 'GBP', 'KZT')")
        if any(column["name"] == "delivery_key" for column in inspector.get_columns("email_outbox")):
            return

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
