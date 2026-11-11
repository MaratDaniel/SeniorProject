"""Request and response bodies. Every request model forbids unknown fields (no mass assignment)."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, PlainSerializer, StringConstraints

# Money goes out as a two-decimal string and comes in as an exact decimal (string or number).
MoneyOut = Annotated[Decimal, PlainSerializer(lambda v: f"{v:.2f}", return_type=str, when_used="always")]
MoneyIn = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]

Trimmed = Annotated[str, StringConstraints(strip_whitespace=True)]
AuctionFormat = Literal["english", "dutch", "sealed_first_price", "vickrey"]


class In(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- accounts ----------


class RegisterIn(In):
    email: EmailStr = Field(max_length=320)
    password: str = Field(max_length=128)
    role: Literal["buyer", "seller"]


class EmailIn(In):
    email: EmailStr = Field(max_length=320)


class TokenIn(In):
    token: str = Field(min_length=10, max_length=200)


class LoginIn(In):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class LoginMfaIn(In):
    mfa_ticket: str = Field(min_length=10, max_length=2000)
    code: str = Field(min_length=6, max_length=20)


class CodeIn(In):
    code: str = Field(min_length=6, max_length=20)


class ResetPasswordIn(In):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(max_length=128)


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    email_verified: bool
    mfa_enabled: bool
    created_at: datetime


class UserEnvelope(BaseModel):
    user: UserOut


class AuthOk(BaseModel):
    status: Literal["ok"] = "ok"
    access_token: str
    user: UserOut


class MfaRequired(BaseModel):
    status: Literal["mfa_required"] = "mfa_required"
    mfa_ticket: str


class RefreshOut(BaseModel):
    access_token: str
    user: UserOut


class MfaSetupOut(BaseModel):
    secret: str
    otpauth_uri: str
    qr_svg: str


class RecoveryCodesOut(BaseModel):
    recovery_codes: list[str]


# ---------- listings and auctions ----------


class CategoryOut(BaseModel):
    slug: str
    name: str


class ImageOut(BaseModel):
    id: int
    url: str


class ListingCreateIn(In):
    title: Annotated[Trimmed, StringConstraints(min_length=3, max_length=80)]
    description: Annotated[Trimmed, StringConstraints(max_length=4000)] = ""
    category: str = Field(max_length=32)
    starting_price: MoneyIn
    reserve_price: MoneyIn | None = None
    image_ids: list[int] = Field(default_factory=list, max_length=8)


class ListingUpdateIn(In):
    title: Annotated[Trimmed, StringConstraints(min_length=3, max_length=80)] | None = None
    description: Annotated[Trimmed, StringConstraints(max_length=4000)] | None = None
    category: str | None = Field(default=None, max_length=32)
    starting_price: MoneyIn | None = None
    reserve_price: MoneyIn | None = None
    image_ids: list[int] | None = Field(default=None, max_length=8)


class ListingOut(BaseModel):
    id: int
    title: str
    description: str
    category: str
    starting_price: MoneyOut
    reserve_price: MoneyOut | None
    images: list[ImageOut]
    status: str
    auction_id: int | None
    created_at: datetime


class AuctionCreateIn(In):
    format: AuctionFormat
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    min_increment: MoneyIn


class BidIn(In):
    amount: MoneyIn


class AuctionCardOut(BaseModel):
    id: int
    listing_id: int
    title: str
    category: str
    cover_url: str | None
    format: str
    status: str
    starting_price: MoneyOut
    current_price: MoneyOut | None
    bid_count: int
    starts_at: datetime
    ends_at: datetime
    reserve_met: bool | None


class BidOut(BaseModel):
    bidder_number: int
    amount: MoneyOut
    placed_at: datetime


class ViewerOut(BaseModel):
    is_seller: bool
    bidder_number: int | None
    is_leader: bool
    transaction_id: int | None


class AuctionDetailOut(AuctionCardOut):
    description: str
    images: list[ImageOut]
    min_increment: MoneyOut
    min_next_bid: MoneyOut | None
    server_time: datetime
    bids: list[BidOut]
    leader_bidder_number: int | None
    winner_bidder_number: int | None
    final_price: MoneyOut | None
    closed_at: datetime | None
    viewer: ViewerOut | None


class AuctionPage(BaseModel):
    items: list[AuctionCardOut]
    total: int
    page: int
    page_size: int


class PlaceBidOut(BaseModel):
    bid: BidOut
    auction: AuctionDetailOut


# ---------- checkout ----------


class DeliveryIn(In):
    full_name: Annotated[Trimmed, StringConstraints(min_length=1, max_length=120)]
    address: Annotated[Trimmed, StringConstraints(min_length=1, max_length=200)]
    city: Annotated[Trimmed, StringConstraints(min_length=1, max_length=80)]
    postal_code: Annotated[Trimmed, StringConstraints(min_length=1, max_length=20)]


class ConfirmIn(In):
    code: str = Field(min_length=6, max_length=10)
    delivery: DeliveryIn


class DeliveryOut(BaseModel):
    full_name: str
    address: str
    city: str
    postal_code: str


class TransactionOut(BaseModel):
    id: int
    reference: str
    auction_id: int
    title: str
    cover_url: str | None
    amount: MoneyOut
    status: str
    role: Literal["buyer", "seller"]
    created_at: datetime
    expires_at: datetime
    completed_at: datetime | None
    won_at: datetime
    delivery: DeliveryOut | None


# ---------- admin and dev ----------


class AuditOut(BaseModel):
    id: int
    at: datetime
    actor_id: int | None
    action: str
    target_type: str | None
    target_id: int | None
    data: dict[str, Any]


class OutboxOut(BaseModel):
    id: int
    to: str
    subject: str
    body: str
    links: list[str]
    created_at: datetime
