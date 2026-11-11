"""The engine core: locking, the server clock, shared rules and the close (NFR-1, NFR-2).

Every function here runs inside the caller's database transaction
(`async with session.begin():`) and returns the live-update events to publish
AFTER the commit. Bids and the close take the same row lock on the auction
(SELECT ... FOR UPDATE), so they are applied one at a time per auction, each
checked against the state the previous one left behind.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.db import db_now
from app.engine.base import BidRejected, RankedBid, StrategyRegistry
from app.errors import not_found
from app.mail import queue_email
from app.models import (
    OPEN_STATUSES,
    Auction,
    AuctionParticipant,
    AuctionStatus,
    Bid,
    Listing,
    Transaction,
    TransactionStatus,
    User,
)
from app.schemas import BidOut
from app.views import bidder_numbers, reserve_met, state_of


@dataclass
class BidResult:
    bid: Bid
    events: list[dict[str, Any]] = field(default_factory=list)


async def lock_auction(session: AsyncSession, auction_id: int) -> Auction | None:
    """Lock the auction row and reload it from the database (never from the identity map)."""
    stmt = (
        select(Auction)
        .where(Auction.id == auction_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


async def _bidder_number(session: AsyncSession, auction_id: int, user_id: int) -> int:
    """Number bidders 1, 2, 3 ... in order of their first bid.

    Safe without extra locking because participants of an auction are only written
    while its row is locked; the unique constraint on (auction_id, number) backs this up.
    """
    existing = await session.scalar(
        select(AuctionParticipant.number).where(
            AuctionParticipant.auction_id == auction_id, AuctionParticipant.user_id == user_id
        )
    )
    if existing is not None:
        return existing
    highest = await session.scalar(
        select(func.coalesce(func.max(AuctionParticipant.number), 0)).where(AuctionParticipant.auction_id == auction_id)
    )
    number = int(highest or 0) + 1
    session.add(AuctionParticipant(auction_id=auction_id, user_id=user_id, number=number))
    return number


async def place_bid(
    session: AsyncSession,
    registry: StrategyRegistry,
    *,
    auction_id: int,
    bidder: User,
    amount: Decimal,
    ip: str | None = None,
) -> BidResult:
    auction = await lock_auction(session, auction_id)  # concurrent bids on this auction wait here
    if auction is None:
        raise not_found("This auction does not exist.")
    listing = await session.get(Listing, auction.listing_id, populate_existing=True)
    assert listing is not None
    now = await db_now(session)  # DR-1: the server clock decides, after the lock is held

    # Rules shared by every format.
    if auction.status == AuctionStatus.CANCELLED:
        raise BidRejected("auction_cancelled", "This auction was cancelled.")
    if auction.status not in OPEN_STATUSES or now >= auction.ends_at:
        raise BidRejected("auction_ended", "This auction has closed.")  # FR-20: strictly before the end
    if now < auction.starts_at:
        raise BidRejected("auction_not_started", "This auction has not opened yet.", {"starts_at": _iso(auction.starts_at)})
    if listing.seller_id == bidder.id:
        raise BidRejected("seller_cannot_bid", "You cannot bid on your own auction.")  # FR-22, DR-7

    strategy = registry.get(auction.format)
    decision = strategy.accept_bid(state_of(auction, listing), bidder_id=bidder.id, amount=amount, now=now)

    events: list[dict[str, Any]] = []
    if auction.status == AuctionStatus.SCHEDULED:
        auction.status = AuctionStatus.ACTIVE  # the scheduler may not have flipped it yet
        events.append({"type": "status_changed", "auction_id": auction.id, "status": AuctionStatus.ACTIVE.value})

    number = await _bidder_number(session, auction.id, bidder.id)
    bid = Bid(auction_id=auction.id, bidder_id=bidder.id, amount=amount, placed_at=now, bidder_number=number)
    session.add(bid)

    extended = decision.ends_at != auction.ends_at
    auction.current_price = decision.price
    auction.leader_id = decision.leader_id
    auction.bid_count += 1
    auction.ends_at = decision.ends_at
    await session.flush()

    audit.record(
        session,
        "bid.accepted",
        actor_id=bidder.id,
        target_type="auction",
        target_id=auction.id,
        ip=ip,
        data={"bid_id": bid.id, "amount": f"{amount:.2f}", "bidder_number": number, "extended": extended},
    )

    leader_number = number if decision.leader_id == bidder.id else (await bidder_numbers(session, auction.id, [decision.leader_id])).get(decision.leader_id)
    events.append(
        {
            "type": "bid_placed",
            "auction_id": auction.id,
            "bid": BidOut(bidder_number=number, amount=amount, placed_at=now).model_dump(mode="json"),
            "current_price": f"{auction.current_price:.2f}",
            "min_next_bid": f"{strategy.min_next_bid(state_of(auction, listing)):.2f}",
            "bid_count": auction.bid_count,
            "reserve_met": reserve_met(listing, auction.current_price),
            "leader_bidder_number": leader_number,
            "ends_at": _iso(auction.ends_at),
        }
    )
    if extended:
        events.append({"type": "time_extended", "auction_id": auction.id, "ends_at": _iso(auction.ends_at)})
    return BidResult(bid=bid, events=events)


async def close_auction(
    session: AsyncSession,
    registry: StrategyRegistry,
    auction_id: int,
    *,
    transaction_expiry: timedelta,
    frontend_url: str,
) -> list[dict[str, Any]]:
    """Close one auction if it is open and past its end time (UC-7). Safe to run any number of times."""
    auction = await lock_auction(session, auction_id)  # the same lock bids take: a bid and the close cannot interleave
    if auction is None or auction.status not in OPEN_STATUSES:
        return []  # already final: nothing to do
    now = await db_now(session)
    if now < auction.ends_at:
        return []  # a sniping extension moved the end; try again later
    listing = await session.get(Listing, auction.listing_id, populate_existing=True)
    assert listing is not None

    strategy = registry.get(auction.format)
    rows = await session.scalars(
        select(Bid).where(Bid.auction_id == auction.id).order_by(Bid.amount.desc(), Bid.placed_at, Bid.id).limit(10)
    )
    ranked = [RankedBid(id=b.id, bidder_id=b.bidder_id, amount=b.amount, placed_at=b.placed_at) for b in rows]
    outcome = strategy.determine_result(state_of(auction, listing), ranked)

    seller = await session.get(User, listing.seller_id)
    assert seller is not None
    auction.closed_at = now
    sold = outcome.winner_id is not None and outcome.price is not None and (
        listing.reserve_price is None or outcome.price >= listing.reserve_price  # FR-18: shared reserve check
    )

    if sold:
        assert outcome.winner_id is not None and outcome.price is not None
        auction.status = AuctionStatus.CLOSED
        auction.winner_id = outcome.winner_id
        auction.final_price = outcome.price
        tx = Transaction(
            auction_id=auction.id,
            buyer_id=outcome.winner_id,
            seller_id=listing.seller_id,
            amount=outcome.price,
            status=TransactionStatus.PENDING,
            created_at=now,
            expires_at=now + transaction_expiry,
        )
        session.add(tx)
        await session.flush()  # the unique auction_id makes a second transaction impossible
        winner = await session.get(User, outcome.winner_id)
        assert winner is not None
        winner_number = (await bidder_numbers(session, auction.id, [winner.id])).get(winner.id)
        audit.record(
            session,
            "auction.closed",
            target_type="auction",
            target_id=auction.id,
            data={"winner_id": winner.id, "final_price": f"{outcome.price:.2f}", "transaction_id": tx.id},
        )
        queue_email(
            session,
            to=winner.email,
            subject=f"You won: {listing.title}",
            body=(
                f"You won \"{listing.title}\" at {outcome.price:.2f}.\n\n"
                f"Complete the purchase within {int(transaction_expiry.total_seconds() // 3600)} hours: "
                f"{frontend_url}/checkout/{tx.id}\n"
            ),
        )
        queue_email(
            session,
            to=seller.email,
            subject=f"Sold: {listing.title}",
            body=f"\"{listing.title}\" sold at {outcome.price:.2f}. The buyer has been asked to complete checkout.\n",
        )
        return [
            {
                "type": "auction_closed",
                "auction_id": auction.id,
                "status": AuctionStatus.CLOSED.value,
                "final_price": f"{outcome.price:.2f}",
                "winner_bidder_number": winner_number,
                "closed_at": _iso(now),
            }
        ]

    auction.status = AuctionStatus.NO_SALE
    reason = "no_bids" if outcome.winner_id is None else "reserve_not_met"
    audit.record(session, "auction.no_sale", target_type="auction", target_id=auction.id, data={"reason": reason})
    queue_email(
        session,
        to=seller.email,
        subject=f"No sale: {listing.title}",
        body=f"\"{listing.title}\" closed without a sale ({reason.replace('_', ' ')}).\n",
    )
    return [
        {
            "type": "auction_closed",
            "auction_id": auction.id,
            "status": AuctionStatus.NO_SALE.value,
            "final_price": None,
            "winner_bidder_number": None,
            "closed_at": _iso(now),
        }
    ]
