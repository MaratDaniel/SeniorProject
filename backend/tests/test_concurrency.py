"""NFR-1: under simultaneous bids there is always one correct winner and price.

These tests send real concurrent requests at one auction; PostgreSQL row locking
must serialize them. They are the evidence for the "one winner, one price" claim.
"""

import asyncio
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.engine.service import close_auction
from app.models import Auction, Bid, Transaction
from tests.conftest import make_auction, move_end

pytestmark = pytest.mark.anyio
BIDDERS = 25


async def test_many_identical_bids_at_once_accept_exactly_one(client: AsyncClient, app, accounts) -> None:  # type: ignore[no-untyped-def]
    seller = await accounts("seller")
    buyers = [await accounts("buyer") for _ in range(BIDDERS)]
    auction_id = await make_auction(app, seller, starting="100.00", step="5.00")

    responses = await asyncio.gather(
        *(client.post(f"/api/auctions/{auction_id}/bids", headers=b.headers, json={"amount": "100.00"}) for b in buyers)
    )
    statuses = sorted(r.status_code for r in responses)
    assert statuses.count(201) == 1, statuses
    assert {r.json()["error"]["code"] for r in responses if r.status_code != 201} == {"bid_too_low"}

    async with app.state.sessionmaker() as session:
        auction = await session.get(Auction, auction_id)
        stored = await session.scalar(select(func.count()).select_from(Bid).where(Bid.auction_id == auction_id))
    assert (auction.bid_count, stored, auction.current_price) == (1, 1, Decimal("100.00"))


async def test_a_burst_of_rising_bids_never_loses_or_reorders_a_bid(client: AsyncClient, app, accounts) -> None:  # type: ignore[no-untyped-def]
    seller = await accounts("seller")
    buyers = [await accounts("buyer") for _ in range(BIDDERS)]
    auction_id = await make_auction(app, seller, starting="100.00", step="1.00")
    amounts = [Decimal("100.00") + Decimal(i * 3) for i in range(BIDDERS)]

    responses = await asyncio.gather(
        *(
            client.post(f"/api/auctions/{auction_id}/bids", headers=b.headers, json={"amount": f"{amount:.2f}"})
            for b, amount in zip(buyers, amounts, strict=True)
        )
    )
    accepted = [Decimal(r.json()["bid"]["amount"]) for r in responses if r.status_code == 201]
    assert accepted, [r.text for r in responses]

    async with app.state.sessionmaker() as session:
        auction = await session.get(Auction, auction_id)
        rows = list(await session.scalars(select(Bid).where(Bid.auction_id == auction_id).order_by(Bid.placed_at, Bid.id)))
    stored = [b.amount for b in rows]
    assert sorted(stored) == sorted(accepted)  # every accepted bid is stored, nothing else is
    assert all(later >= earlier + Decimal("1.00") for earlier, later in zip(stored, stored[1:], strict=False))  # applied in order
    assert auction.current_price == max(accepted) and auction.bid_count == len(accepted)
    assert len({b.bidder_number for b in rows}) == len(rows)  # one number per bidder


async def test_closing_many_times_at_once_creates_one_transaction(app, accounts) -> None:  # type: ignore[no-untyped-def]
    seller, alice = await accounts("seller"), await accounts("buyer")
    auction_id = await make_auction(app, seller, starting="100.00")
    from app.engine.service import place_bid

    async with app.state.sessionmaker() as session, session.begin():
        from app.models import User

        await place_bid(session, app.state.strategies, auction_id=auction_id, bidder=await session.get(User, alice.id), amount=Decimal("100.00"))
    await move_end(app, auction_id, -1)

    async def close_once() -> list[dict]:
        async with app.state.sessionmaker() as session, session.begin():
            return await close_auction(session, app.state.strategies, auction_id, transaction_expiry=timedelta(hours=48), frontend_url="http://x")

    results = await asyncio.gather(*(close_once() for _ in range(10)))
    assert sum(1 for events in results if events) == 1  # exactly one close did the work
    async with app.state.sessionmaker() as session:
        count = await session.scalar(select(func.count()).select_from(Transaction).where(Transaction.auction_id == auction_id))
        auction = await session.get(Auction, auction_id)
    assert count == 1 and auction.status == "closed" and auction.winner_id == alice.id


async def test_bids_racing_the_close_are_either_in_or_refused(client: AsyncClient, app, accounts) -> None:  # type: ignore[no-untyped-def]
    seller = await accounts("seller")
    buyers = [await accounts("buyer") for _ in range(10)]
    auction_id = await make_auction(app, seller, starting="100.00", step="1.00")
    await move_end(app, auction_id, 0.3)

    async def close_soon() -> list[dict]:
        await asyncio.sleep(0.3)
        async with app.state.sessionmaker() as session, session.begin():
            return await close_auction(session, app.state.strategies, auction_id, transaction_expiry=timedelta(hours=48), frontend_url="http://x")

    bids = [
        client.post(f"/api/auctions/{auction_id}/bids", headers=b.headers, json={"amount": f"{100 + i * 2}.00"})
        for i, b in enumerate(buyers)
    ]
    *responses, _ = await asyncio.gather(*bids, close_soon())
    for _ in range(20):  # sniping may have moved the end: close again until it really closes
        async with app.state.sessionmaker() as session:
            auction = await session.get(Auction, auction_id)
        if auction.status != "active":
            break
        await move_end(app, auction_id, -1)
        await close_soon()
    async with app.state.sessionmaker() as session:
        auction = await session.get(Auction, auction_id)
        top = await session.scalar(select(func.max(Bid.amount)).where(Bid.auction_id == auction_id))
        late = await session.scalar(select(func.count()).select_from(Bid).where(Bid.auction_id == auction_id, Bid.placed_at >= auction.closed_at))
    accepted = [r for r in responses if r.status_code == 201]
    assert late == 0  # no bid was stored after the close
    if accepted:
        assert auction.status == "closed" and auction.final_price == top
    else:
        assert auction.status == "no_sale"
