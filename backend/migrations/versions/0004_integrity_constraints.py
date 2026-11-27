"""Let the database refuse rows that break an invariant.

Until now these rules were kept only by application code. Each one becomes a
constraint, so a bug, a script or a manual UPDATE cannot leave a listing in an
unknown category, an auction half-closed, or a bid under another bidder's number.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, constraint name, condition)
CHECKS = [
    (
        "listings",
        "ck_listings_category",
        "category IN ('art', 'antiques', 'collectibles', 'furniture', 'books', 'electronics', 'fashion', 'home', 'other')",
    ),
    ("auctions", "ck_auctions_format", "format IN ('english', 'dutch', 'sealed_first_price', 'vickrey')"),
    # Sniping protection only ever moves the end later.
    ("auctions", "ck_auctions_end_only_extends", "ends_at >= original_ends_at"),
    ("auctions", "ck_auctions_leader_with_price", "(leader_id IS NULL) = (current_price IS NULL)"),
    (
        "auctions",
        "ck_auctions_winner_only_when_closed",
        "(status = 'closed') = (winner_id IS NOT NULL) AND (winner_id IS NULL) = (final_price IS NULL)",
    ),
    ("auctions", "ck_auctions_closed_at_when_final", "(status IN ('closed', 'no_sale', 'cancelled')) = (closed_at IS NOT NULL)"),
    ("bids", "ck_bids_bidder_number_positive", "bidder_number > 0"),
    ("transactions", "ck_transactions_completed_at_when_completed", "(status = 'completed') = (completed_at IS NOT NULL)"),
    ("users", "ck_users_failed_logins_non_negative", "failed_logins >= 0"),
    ("users", "ck_users_mfa_enabled_has_secret", "NOT mfa_enabled OR mfa_secret_enc IS NOT NULL"),
]


def upgrade() -> None:
    for table, name, condition in CHECKS:
        op.create_check_constraint(op.f(name), table, condition)
    # bids.bidder_number repeats auction_participants.number so bid history needs no join.
    # The composite key guarantees the copy always equals the participant's number.
    op.create_unique_constraint("uq_auction_participants_identity", "auction_participants", ["auction_id", "user_id", "number"])
    op.create_foreign_key(
        "fk_bids_participant",
        "bids",
        "auction_participants",
        ["auction_id", "bidder_id", "bidder_number"],
        ["auction_id", "user_id", "number"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_bids_participant", "bids", type_="foreignkey")
    op.drop_constraint("uq_auction_participants_identity", "auction_participants", type_="unique")
    for table, name, _ in reversed(CHECKS):
        op.drop_constraint(op.f(name), table, type_="check")
