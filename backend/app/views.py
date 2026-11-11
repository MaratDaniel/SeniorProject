"""Read models: turn rows into the API shapes in docs/API.md."""

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import db_now
from app.engine.base import AuctionState, StrategyRegistry
from app.models import (
    OPEN_STATUSES,
    Auction,
    AuctionParticipant,
    Bid,
    Listing,
    ListingImage,
    Transaction,
    User,
)
from app.schemas import (
    AuctionCardOut,
    AuctionDetailOut,
    BidOut,
    DeliveryOut,
    ImageOut,
    ListingOut,
    TransactionOut,
    UserOut,
    ViewerOut,
)


def media_url(storage_key: str) -> str:
    return f"/media/{storage_key}"


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        email_verified=user.email_verified_at is not None,
        mfa_enabled=user.mfa_enabled,
        created_at=user.created_at,
    )


def reserve_met(listing: Listing, current_price: Decimal | None) -> bool | None:
    if listing.reserve_price is None:
        return None
    return current_price is not None and current_price >= listing.reserve_price


def state_of(auction: Auction, listing: Listing) -> AuctionState:
    return AuctionState(
        starts_at=auction.starts_at,
        ends_at=auction.ends_at,
        starting_price=listing.starting_price,
        min_increment=auction.min_increment,
        current_price=auction.current_price,
        leader_id=auction.leader_id,
        bid_count=auction.bid_count,
    )


async def images_for(session: AsyncSession, listing_ids: Iterable[int]) -> dict[int, list[ListingImage]]:
    ids = list(set(listing_ids))
    if not ids:
        return {}
    rows = await session.scalars(
        select(ListingImage)
        .where(ListingImage.listing_id.in_(ids))
        .order_by(ListingImage.listing_id, ListingImage.position, ListingImage.id)
    )
    grouped: dict[int, list[ListingImage]] = {i: [] for i in ids}
    for image in rows:
        grouped[image.listing_id].append(image)  # type: ignore[index]
    return grouped


def card(auction: Auction, listing: Listing, images: list[ListingImage]) -> AuctionCardOut:
    return AuctionCardOut(
        id=auction.id,
        listing_id=listing.id,
        title=listing.title,
        category=listing.category,
        cover_url=media_url(images[0].storage_key) if images else None,
        format=auction.format,
        status=auction.status,
        starting_price=listing.starting_price,
        current_price=auction.current_price,
        bid_count=auction.bid_count,
        starts_at=auction.starts_at,
        ends_at=auction.ends_at,
        reserve_met=reserve_met(listing, auction.current_price),
    )


async def cards(session: AsyncSession, rows: list[tuple[Auction, Listing]]) -> list[AuctionCardOut]:
    images = await images_for(session, (listing.id for _, listing in rows))
    return [card(auction, listing, images.get(listing.id, [])) for auction, listing in rows]


async def bidder_numbers(session: AsyncSession, auction_id: int, user_ids: Iterable[int | None]) -> dict[int, int]:
    ids = [u for u in set(user_ids) if u is not None]
    if not ids:
        return {}
    rows = await session.execute(
        select(AuctionParticipant.user_id, AuctionParticipant.number).where(
            AuctionParticipant.auction_id == auction_id, AuctionParticipant.user_id.in_(ids)
        )
    )
    return {user_id: number for user_id, number in rows}


async def load_auction_detail(
    session: AsyncSession,
    registry: StrategyRegistry,
    auction_id: int,
    viewer: User | None,
) -> AuctionDetailOut | None:
    row = (
        await session.execute(
            select(Auction, Listing).join(Listing, Listing.id == Auction.listing_id).where(Auction.id == auction_id)
        )
    ).one_or_none()
    if row is None:
        return None
    auction, listing = row
    images = (await images_for(session, [listing.id]))[listing.id]
    strategy = registry.get(auction.format)
    now = await db_now(session)

    bids: list[Bid] = []
    if strategy.bids_visible:
        bids = list(
            await session.scalars(
                select(Bid).where(Bid.auction_id == auction.id).order_by(Bid.placed_at.desc(), Bid.id.desc()).limit(50)
            )
        )
    numbers = await bidder_numbers(session, auction.id, [auction.leader_id, auction.winner_id, viewer.id if viewer else None])

    open_now = auction.status in OPEN_STATUSES and auction.starts_at <= now < auction.ends_at
    min_next = strategy.min_next_bid(state_of(auction, listing)) if open_now else None

    viewer_out: ViewerOut | None = None
    if viewer is not None:
        transaction_id = None
        if auction.winner_id is not None and viewer.id in (auction.winner_id, listing.seller_id):
            transaction_id = await session.scalar(select(Transaction.id).where(Transaction.auction_id == auction.id))
        viewer_out = ViewerOut(
            is_seller=viewer.id == listing.seller_id,
            bidder_number=numbers.get(viewer.id),
            is_leader=auction.leader_id == viewer.id and auction.status in OPEN_STATUSES,
            transaction_id=transaction_id,
        )

    base = card(auction, listing, images)
    return AuctionDetailOut(
        **base.model_dump(),
        description=listing.description,
        images=[ImageOut(id=i.id, url=media_url(i.storage_key)) for i in images],
        min_increment=auction.min_increment,
        min_next_bid=min_next,
        server_time=now,
        bids=[BidOut(bidder_number=b.bidder_number, amount=b.amount, placed_at=b.placed_at) for b in bids],
        leader_bidder_number=numbers.get(auction.leader_id) if auction.leader_id else None,
        winner_bidder_number=numbers.get(auction.winner_id) if auction.winner_id else None,
        final_price=auction.final_price,
        closed_at=auction.closed_at,
        viewer=viewer_out,
    )


async def load_auction_public(session: AsyncSession, registry: StrategyRegistry, auction_id: int) -> dict[str, Any] | None:
    detail = await load_auction_detail(session, registry, auction_id, viewer=None)
    if detail is None:
        return None
    return detail.model_dump(mode="json", exclude={"viewer"})


async def load_listing(session: AsyncSession, listing_id: int, viewer: User | None) -> ListingOut | None:
    listing = await session.get(Listing, listing_id)
    if listing is None:
        return None
    images = (await images_for(session, [listing.id]))[listing.id]
    auction_id = await session.scalar(select(Auction.id).where(Auction.listing_id == listing.id))
    is_owner = viewer is not None and viewer.id == listing.seller_id
    return ListingOut(
        id=listing.id,
        title=listing.title,
        description=listing.description,
        category=listing.category,
        starting_price=listing.starting_price,
        reserve_price=listing.reserve_price if is_owner else None,  # never shown to bidders (FR-39)
        images=[ImageOut(id=i.id, url=media_url(i.storage_key)) for i in images],
        status=listing.status,
        auction_id=auction_id,
        created_at=listing.created_at,
    )


def transaction_out(tx: Transaction, auction: Auction, listing: Listing, cover: str | None, viewer_id: int) -> TransactionOut:
    return TransactionOut(
        id=tx.id,
        reference=f"TX-{tx.id:06d}",
        auction_id=tx.auction_id,
        title=listing.title,
        cover_url=cover,
        amount=tx.amount,
        status=tx.status,
        role="buyer" if tx.buyer_id == viewer_id else "seller",
        created_at=tx.created_at,
        expires_at=tx.expires_at,
        completed_at=tx.completed_at,
        won_at=auction.closed_at or tx.created_at,
        delivery=DeliveryOut(**tx.delivery) if tx.delivery else None,
    )
