"""The database refuses rows that break an invariant, whatever the application code does.

Each case writes around the application with plain SQL, the way a bug or a manual
fix would, and expects PostgreSQL to reject it (migration 0004).
"""

from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.engine.service import place_bid
from app.models import Auction, User
from tests.conftest import make_auction

pytestmark = pytest.mark.anyio

BAD_WRITES = {
    "a category outside the list": "UPDATE listings SET category = 'weapons' WHERE id = :listing",
    "a format the schema does not know": "UPDATE auctions SET format = 'raffle' WHERE id = :auction",
    "an end moved before the original end": "UPDATE auctions SET ends_at = original_ends_at - interval '1 minute' WHERE id = :auction",
    "a price without a leader": "UPDATE auctions SET leader_id = NULL WHERE id = :auction",
    "a winner on an auction that is still open": "UPDATE auctions SET winner_id = :buyer, final_price = 100 WHERE id = :auction",
    "a final status without a closing time": "UPDATE auctions SET status = 'no_sale' WHERE id = :auction",
    "a bid under a number that is not the bidder's": (
        "INSERT INTO bids (auction_id, bidder_id, amount, placed_at, bidder_number) VALUES (:auction, :buyer, 500, now(), 99)"
    ),
    "a completed sale without a completion time": (
        "INSERT INTO transactions (auction_id, buyer_id, seller_id, amount, status, created_at, expires_at) "
        "VALUES (:auction, :buyer, :seller, 100, 'completed', now(), now() + interval '2 days')"
    ),
    "two-step sign-in switched on without a secret": "UPDATE users SET mfa_enabled = true, mfa_secret_enc = NULL WHERE id = :buyer",
}


@pytest.mark.parametrize("statement", BAD_WRITES.values(), ids=BAD_WRITES.keys())
async def test_the_database_refuses(statement: str, app, accounts) -> None:  # type: ignore[no-untyped-def]
    seller, buyer = await accounts("seller"), await accounts("buyer")
    auction_id = await make_auction(app, seller)
    async with app.state.sessionmaker() as session, session.begin():
        await place_bid(
            session, app.state.strategies, auction_id=auction_id, bidder=await session.get(User, buyer.id), amount=Decimal("100.00")
        )
        listing_id = await session.scalar(select(Auction.listing_id).where(Auction.id == auction_id))
    ids = {"auction": auction_id, "listing": listing_id, "buyer": buyer.id, "seller": seller.id}

    with pytest.raises(IntegrityError):
        async with app.state.sessionmaker() as session, session.begin():
            await session.execute(text(statement), {name: ids[name] for name in ids if f":{name}" in statement})

    # The refused statement changed nothing: the bid placed through the engine is still the only one.
    async with app.state.sessionmaker() as session:
        auction = await session.get(Auction, auction_id)
    assert (auction.status, auction.bid_count, auction.leader_id, auction.current_price) == ("active", 1, buyer.id, Decimal("100.00"))
