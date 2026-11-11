"""Browse, auction page and bidding (FR-9, FR-14 to FR-24, FR-32)."""

from typing import Literal

from fastapi import APIRouter, Query, Request
from sqlalchemy import Select, func, or_, select

from app import audit
from app.deps import BrokerDep, CurrentUser, LimiterDep, OptionalUser, SessionDep, SessionmakerDep, StrategiesDep, client_ip, ensure_verified
from app.engine.base import BidRejected
from app.engine.service import place_bid
from app.errors import ApiError, forbidden, not_found
from app.models import Auction, AuctionStatus, Bid, Listing, Role
from app.realtime.broker import channel_for
from app.schemas import AuctionCardOut, AuctionDetailOut, AuctionPage, BidIn, BidOut, PlaceBidOut
from app.views import cards, load_auction_detail

router = APIRouter(prefix="/api", tags=["auctions"])

STATUS_FILTERS: dict[str, tuple[str, ...]] = {
    "live": (AuctionStatus.ACTIVE,),
    "upcoming": (AuctionStatus.SCHEDULED,),
    "ended": (AuctionStatus.CLOSED, AuctionStatus.NO_SALE),
    "all": (AuctionStatus.SCHEDULED, AuctionStatus.ACTIVE, AuctionStatus.CLOSED, AuctionStatus.NO_SALE),
}


def _like_pattern(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("/auctions", response_model=AuctionPage)
async def browse(
    session: SessionDep,
    q: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, max_length=32),
    format: str | None = Query(default=None, max_length=24),
    status: Literal["live", "upcoming", "ended", "all"] = "all",
    sort: Literal["ending_soon", "newest", "price_low", "price_high"] = "ending_soon",
    page: int = Query(default=1, ge=1, le=1000),
    page_size: int = Query(default=24, ge=1, le=48),
) -> AuctionPage:
    stmt: Select = (
        select(Auction, Listing)
        .join(Listing, Listing.id == Auction.listing_id)
        .where(Auction.status.in_(STATUS_FILTERS[status]))
    )
    if q and q.strip():
        pattern = _like_pattern(q.strip())
        stmt = stmt.where(or_(Listing.title.ilike(pattern, escape="\\"), Listing.description.ilike(pattern, escape="\\")))
    if category:
        stmt = stmt.where(Listing.category == category)
    if format:
        stmt = stmt.where(Auction.format == format)

    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    price = func.coalesce(Auction.current_price, Listing.starting_price)
    order = {
        "ending_soon": (Auction.ends_at.asc(), Auction.id.asc()),
        "newest": (Auction.created_at.desc(), Auction.id.desc()),
        "price_low": (price.asc(), Auction.id.asc()),
        "price_high": (price.desc(), Auction.id.desc()),
    }[sort]
    rows = (await session.execute(stmt.order_by(*order).offset((page - 1) * page_size).limit(page_size))).all()
    return AuctionPage(items=await cards(session, list(rows)), total=int(total or 0), page=page, page_size=page_size)


@router.get("/auctions/{auction_id}", response_model=AuctionDetailOut)
async def auction_detail(auction_id: int, viewer: OptionalUser, session: SessionDep, strategies: StrategiesDep) -> AuctionDetailOut:
    out = await load_auction_detail(session, strategies, auction_id, viewer)
    if out is None:
        raise not_found("This auction does not exist.")
    return out


@router.post("/auctions/{auction_id}/bids", status_code=201, response_model=PlaceBidOut)
async def bid(
    auction_id: int,
    body: BidIn,
    request: Request,
    user: CurrentUser,
    session: SessionDep,
    sessionmaker: SessionmakerDep,
    strategies: StrategiesDep,
    broker: BrokerDep,
    limiter: LimiterDep,
) -> PlaceBidOut:
    ensure_verified(user)
    if user.role == Role.ADMIN:
        raise forbidden("Administrator accounts cannot bid.")
    limiter.check(f"bid:{user.id}", 30, 60)
    ip = client_ip(request)
    try:
        async with session.begin():
            result = await place_bid(session, strategies, auction_id=auction_id, bidder=user, amount=body.amount, ip=ip)
    except BidRejected as rejected:
        # The bid's own transaction rolled back; record the refusal separately.
        async with sessionmaker() as audit_session, audit_session.begin():
            audit.record(
                audit_session,
                "bid.rejected",
                actor_id=user.id,
                target_type="auction",
                target_id=auction_id,
                ip=ip,
                data={"amount": f"{body.amount:.2f}", "reason": rejected.code},
            )
        raise ApiError(409, rejected.code, rejected.message, rejected.details) from rejected
    for event in result.events:  # only after the commit (NFR-1)
        await broker.publish(channel_for(auction_id), event)
    detail = await load_auction_detail(session, strategies, auction_id, viewer=user)
    assert detail is not None
    return PlaceBidOut(
        bid=BidOut(bidder_number=result.bid.bidder_number, amount=result.bid.amount, placed_at=result.bid.placed_at),
        auction=detail,
    )


@router.get("/me/listings", response_model=list[AuctionCardOut])
async def my_listings(user: CurrentUser, session: SessionDep) -> list[AuctionCardOut]:
    if user.role != Role.SELLER:
        raise forbidden("Only seller accounts have listings.")
    rows = (
        await session.execute(
            select(Auction, Listing)
            .join(Listing, Listing.id == Auction.listing_id)
            .where(Listing.seller_id == user.id)
            .order_by(Auction.created_at.desc())
            .limit(200)
        )
    ).all()
    return await cards(session, list(rows))


@router.get("/me/bids", response_model=list[AuctionCardOut])
async def my_bids(user: CurrentUser, session: SessionDep) -> list[AuctionCardOut]:
    bid_on = select(Bid.auction_id).where(Bid.bidder_id == user.id).distinct().subquery()
    rows = (
        await session.execute(
            select(Auction, Listing)
            .join(Listing, Listing.id == Auction.listing_id)
            .where(Auction.id.in_(select(bid_on.c.auction_id)))
            .order_by(Auction.ends_at.desc())
            .limit(200)
        )
    ).all()
    return await cards(session, list(rows))
