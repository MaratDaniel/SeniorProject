"""Database schema (SQLAlchemy 2.x typed ORM).

Invariants that matter for correctness live in the database, not only in code:
one auction per listing, one transaction per auction, one bidder number per bidder
per auction, and an audit log that rejects UPDATE and DELETE (trigger in the migration).
"""

import enum
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {
        datetime: DateTime(timezone=True),
        Decimal: Numeric(12, 2),  # money: exact decimals, never floats (DR-9)
        dict[str, Any]: JSONB,
    }


class Role(enum.StrEnum):
    BUYER = "buyer"
    SELLER = "seller"
    ADMIN = "admin"


class ListingStatus(enum.StrEnum):
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"


class AuctionStatus(enum.StrEnum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    CLOSED = "closed"
    NO_SALE = "no_sale"
    CANCELLED = "cancelled"


OPEN_STATUSES = (AuctionStatus.SCHEDULED, AuctionStatus.ACTIVE)
FINAL_STATUSES = (AuctionStatus.CLOSED, AuctionStatus.NO_SALE, AuctionStatus.CANCELLED)


class TransactionStatus(enum.StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    EXPIRED = "expired"


class TokenPurpose(enum.StrEnum):
    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"


def _one_of(column: str, values: type[enum.StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(v.value) for v in values)})"


def _id() -> Mapped[int]:
    return mapped_column(BigInteger, Identity(), primary_key=True)


def _fk(target: str, *, nullable: bool = False, ondelete: str | None = None, **kw: Any) -> Any:
    return mapped_column(BigInteger, ForeignKey(target, ondelete=ondelete), nullable=nullable, **kw)


def _created() -> Mapped[datetime]:
    return mapped_column(server_default=func.now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(_one_of("role", Role), name="role"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    id: Mapped[int] = _id()
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(10))
    email_verified_at: Mapped[datetime | None]
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    mfa_secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary)  # Fernet-encrypted TOTP secret
    mfa_pending_secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    mfa_last_step: Mapped[int | None] = mapped_column(BigInteger)  # last accepted TOTP step: no code is accepted twice
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    locked_until: Mapped[datetime | None]
    created_at: Mapped[datetime] = _created()


class EmailToken(Base):
    __tablename__ = "email_tokens"
    __table_args__ = (CheckConstraint(_one_of("purpose", TokenPurpose), name="purpose"),)

    id: Mapped[int] = _id()
    user_id: Mapped[int] = _fk("users.id", ondelete="CASCADE", index=True)
    purpose: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # SHA-256 of the emailed token
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = _created()


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = _id()
    user_id: Mapped[int] = _fk("users.id", ondelete="CASCADE", index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    revoked_reason: Mapped[str | None] = mapped_column(String(16))  # rotated, logout, reuse, reset
    created_at: Mapped[datetime] = _created()


class RecoveryCode(Base):
    __tablename__ = "recovery_codes"

    id: Mapped[int] = _id()
    user_id: Mapped[int] = _fk("users.id", ondelete="CASCADE", index=True)
    code_hash: Mapped[str] = mapped_column(String(64))  # HMAC-SHA256 with a server key
    used_at: Mapped[datetime | None]


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        CheckConstraint("starting_price > 0", name="starting_price_positive"),
        CheckConstraint("reserve_price IS NULL OR reserve_price >= starting_price", name="reserve_not_below_start"),
        CheckConstraint(_one_of("status", ListingStatus), name="status"),
    )

    id: Mapped[int] = _id()
    seller_id: Mapped[int] = _fk("users.id", index=True)
    title: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    category: Mapped[str] = mapped_column(String(32), index=True)
    starting_price: Mapped[Decimal]
    reserve_price: Mapped[Decimal | None]
    status: Mapped[str] = mapped_column(String(12), default=ListingStatus.ACTIVE, server_default=ListingStatus.ACTIVE.value)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class ListingImage(Base):
    __tablename__ = "listing_images"

    id: Mapped[int] = _id()
    uploader_id: Mapped[int] = _fk("users.id", index=True)
    listing_id: Mapped[int | None] = _fk("listings.id", nullable=True, ondelete="SET NULL", index=True)
    storage_key: Mapped[str] = mapped_column(String(64), unique=True)  # random name, never user input
    content_type: Mapped[str] = mapped_column(String(32))
    size_bytes: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = _created()


class Auction(Base):
    __tablename__ = "auctions"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="schedule"),
        CheckConstraint("min_increment > 0", name="min_increment_positive"),
        CheckConstraint(_one_of("status", AuctionStatus), name="status"),
        CheckConstraint("bid_count >= 0", name="bid_count_non_negative"),
        Index("ix_auctions_status_ends_at", "status", "ends_at"),
        Index("ix_auctions_status_starts_at", "status", "starts_at"),
    )

    id: Mapped[int] = _id()
    listing_id: Mapped[int] = _fk("listings.id", unique=True)  # one auction per listing
    format: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(12), default=AuctionStatus.SCHEDULED)
    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime]  # moves later with sniping protection
    original_ends_at: Mapped[datetime]
    min_increment: Mapped[Decimal]
    current_price: Mapped[Decimal | None]
    leader_id: Mapped[int | None] = _fk("users.id", nullable=True)
    bid_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    winner_id: Mapped[int | None] = _fk("users.id", nullable=True)
    final_price: Mapped[Decimal | None]
    closed_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = _created()


class Bid(Base):
    __tablename__ = "bids"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    id: Mapped[int] = _id()
    auction_id: Mapped[int] = _fk("auctions.id")
    bidder_id: Mapped[int] = _fk("users.id", index=True)
    amount: Mapped[Decimal]
    placed_at: Mapped[datetime]  # database clock at the moment the bid was accepted
    bidder_number: Mapped[int] = mapped_column(Integer)


# Ranking order used to pick a winner (FR-19): highest amount, then earliest, then lowest id.
Index("ix_bids_auction_ranking", Bid.auction_id, Bid.amount.desc(), Bid.placed_at, Bid.id)


class AuctionParticipant(Base):
    """Bidders are shown by number, never by name. Numbers are per auction, in order of first bid."""

    __tablename__ = "auction_participants"
    __table_args__ = (UniqueConstraint("auction_id", "number", name="uq_auction_participants_number"),)

    auction_id: Mapped[int] = _fk("auctions.id", primary_key=True)
    user_id: Mapped[int] = _fk("users.id", primary_key=True)
    number: Mapped[int] = mapped_column(Integer)


class Transaction(Base):
    """The sale created when an auction closes with a winner. Exactly one per auction (FR-34)."""

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(_one_of("status", TransactionStatus), name="status"),
        CheckConstraint("buyer_id <> seller_id", name="distinct_parties"),
        CheckConstraint("amount > 0", name="amount_positive"),
    )

    id: Mapped[int] = _id()
    auction_id: Mapped[int] = _fk("auctions.id", unique=True)
    buyer_id: Mapped[int] = _fk("users.id", index=True)
    seller_id: Mapped[int] = _fk("users.id", index=True)
    amount: Mapped[Decimal]
    status: Mapped[str] = mapped_column(String(12), default=TransactionStatus.PENDING)
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    completed_at: Mapped[datetime | None]
    payment_ref: Mapped[str | None] = mapped_column(String(40))
    delivery: Mapped[dict[str, Any] | None]


class AuditLog(Base):
    """Append-only. The database rejects UPDATE, DELETE and TRUNCATE on this table."""

    __tablename__ = "audit_log"

    id: Mapped[int] = _id()
    at: Mapped[datetime] = mapped_column(server_default=text("clock_timestamp()"))
    actor_id: Mapped[int | None] = mapped_column(BigInteger)  # no foreign key: the log outlives accounts
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[int | None] = mapped_column(BigInteger)
    ip: Mapped[str | None] = mapped_column(String(45))
    data: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))


class EmailOutbox(Base):
    """Outgoing email, written in the same transaction as the event that causes it."""

    __tablename__ = "email_outbox"

    id: Mapped[int] = _id()
    to_address: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    sent_at: Mapped[datetime | None]
