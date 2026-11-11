"""Closing (UC-7, FR-17, FR-18, FR-34) and checkout with a fresh code (UC-8, FR-5, FR-35, NFR-6)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.engine.service import place_bid
from app.models import Auction, EmailOutbox, Transaction, User
from app.scheduler import Scheduler
from tests.conftest import make_auction, move_end

pytestmark = pytest.mark.anyio
DELIVERY = {"full_name": " Aru Bekova ", "address": "12 Abay Avenue", "city": "Almaty", "postal_code": "050000"}


async def bid_directly(app, auction_id: int, account, amount: str) -> None:  # type: ignore[no-untyped-def]
    async with app.state.sessionmaker() as session, session.begin():
        bidder = await session.get(User, account.id)
        await place_bid(session, app.state.strategies, auction_id=auction_id, bidder=bidder, amount=Decimal(amount))


def scheduler(app) -> Scheduler:  # type: ignore[no-untyped-def]
    return Scheduler(app.state.sessionmaker, app.state.broker, app.state.strategies, app.state.settings)


async def sold_auction(app, seller, buyer, amount: str = "120.00") -> int:  # type: ignore[no-untyped-def]
    auction_id = await make_auction(app, seller, starting="100.00")
    await bid_directly(app, auction_id, buyer, amount)
    await move_end(app, auction_id, -1)
    assert auction_id in await scheduler(app).close_due()
    return auction_id


async def test_the_scheduler_opens_and_closes_on_time(app, accounts) -> None:  # type: ignore[no-untyped-def]
    seller = await accounts("seller")
    upcoming = await make_auction(app, seller, starts_in=timedelta(hours=1), ends_in=timedelta(hours=2))
    async with app.state.sessionmaker() as session, session.begin():
        await session.execute(text("UPDATE auctions SET starts_at = clock_timestamp() - interval '1 second' WHERE id = :id"), {"id": upcoming})
    assert upcoming in await scheduler(app).open_due()

    empty = await make_auction(app, seller)
    await move_end(app, empty, -1)
    await scheduler(app).close_due()
    async with app.state.sessionmaker() as session:
        assert (await session.get(Auction, empty)).status == "no_sale"  # FR-18: no bids, no sale


async def test_reserve_not_met_is_no_sale(app, accounts) -> None:  # type: ignore[no-untyped-def]
    seller, buyer = await accounts("seller"), await accounts("buyer")
    auction_id = await make_auction(app, seller, starting="100.00", reserve="300.00")
    await bid_directly(app, auction_id, buyer, "150.00")
    await move_end(app, auction_id, -1)
    await scheduler(app).close_due()
    async with app.state.sessionmaker() as session:
        auction = await session.get(Auction, auction_id)
        tx = await session.scalar(select(Transaction).where(Transaction.auction_id == auction_id))
    assert auction.status == "no_sale" and tx is None


async def test_a_sale_creates_one_pending_transaction_and_emails(app, accounts) -> None:  # type: ignore[no-untyped-def]
    seller, buyer = await accounts("seller"), await accounts("buyer")
    auction_id = await sold_auction(app, seller, buyer, "120.00")
    async with app.state.sessionmaker() as session:
        auction = await session.get(Auction, auction_id)
        tx = await session.scalar(select(Transaction).where(Transaction.auction_id == auction_id))
        subjects = list(await session.scalars(select(EmailOutbox.subject).where(EmailOutbox.to_address.in_([buyer.email, seller.email]))))
    assert auction.status == "closed" and auction.final_price == Decimal("120.00")
    assert tx.status == "pending" and tx.buyer_id == buyer.id and tx.expires_at - tx.created_at == timedelta(hours=48)
    assert sorted(subjects) == ["Sold: Brass balance", "You won: Brass balance"]


async def test_checkout_needs_a_fresh_code_and_completes_once(client: AsyncClient, app, accounts) -> None:  # type: ignore[no-untyped-def]
    seller, buyer = await accounts("seller"), await accounts("buyer")
    await sold_auction(app, seller, buyer)
    async with app.state.sessionmaker() as session:
        tx_id = await session.scalar(select(Transaction.id).where(Transaction.buyer_id == buyer.id))
    url = f"/api/transactions/{tx_id}/confirm"

    wrong = await client.post(url, headers=buyer.headers, json={"code": "000000", "delivery": DELIVERY})
    assert wrong.status_code == 400 and wrong.json()["error"]["code"] == "invalid_code"
    seller_view = await client.post(url, headers=seller.headers, json={"code": seller.code(), "delivery": DELIVERY})
    assert seller_view.status_code == 404  # only the buyer can pay

    done = await client.post(url, headers=buyer.headers, json={"code": buyer.code(), "delivery": DELIVERY})
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "completed" and body["reference"] == f"TX-{tx_id:06d}" and body["delivery"]["full_name"] == "Aru Bekova"

    again = await client.post(url, headers=buyer.headers, json={"code": buyer.code(1), "delivery": DELIVERY})
    assert again.status_code == 409 and again.json()["error"]["code"] == "transaction_not_pending"
    assert (await client.get(f"/api/transactions/{tx_id}", headers=seller.headers)).json()["role"] == "seller"


async def test_a_used_code_cannot_pay(client: AsyncClient, app, accounts) -> None:  # type: ignore[no-untyped-def]
    seller, buyer = await accounts("seller"), await accounts("buyer")
    await sold_auction(app, seller, buyer)
    async with app.state.sessionmaker() as session, session.begin():
        await session.execute(text("UPDATE users SET mfa_last_step = :s WHERE id = :id"), {"s": 10**12, "id": buyer.id})
        tx_id = await session.scalar(select(Transaction.id).where(Transaction.buyer_id == buyer.id))
    replay = await client.post(f"/api/transactions/{tx_id}/confirm", headers=buyer.headers, json={"code": buyer.code(), "delivery": DELIVERY})
    assert replay.status_code == 400 and replay.json()["error"]["code"] == "invalid_code"


async def test_no_two_step_or_expired_cannot_pay(client: AsyncClient, app, accounts) -> None:  # type: ignore[no-untyped-def]
    seller = await accounts("seller")
    no_mfa = await accounts("buyer", mfa=False)
    await sold_auction(app, seller, no_mfa)
    async with app.state.sessionmaker() as session:
        tx_id = await session.scalar(select(Transaction.id).where(Transaction.buyer_id == no_mfa.id))
    blocked = await client.post(f"/api/transactions/{tx_id}/confirm", headers=no_mfa.headers, json={"code": "123456", "delivery": DELIVERY})
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "mfa_required"

    buyer = await accounts("buyer")
    await sold_auction(app, seller, buyer)
    async with app.state.sessionmaker() as session, session.begin():
        tx_id = await session.scalar(select(Transaction.id).where(Transaction.buyer_id == buyer.id))
        await session.execute(text("UPDATE transactions SET expires_at = clock_timestamp() - interval '1 second' WHERE id = :id"), {"id": tx_id})
    late = await client.post(f"/api/transactions/{tx_id}/confirm", headers=buyer.headers, json={"code": buyer.code(), "delivery": DELIVERY})
    assert late.status_code == 410
    async with app.state.sessionmaker() as session:
        assert (await session.get(Transaction, tx_id)).status == "expired"


async def test_the_audit_log_cannot_be_changed(app, accounts) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy.exc import DBAPIError

    await accounts("buyer")
    async with app.state.sessionmaker() as session, session.begin():
        await session.execute(text("INSERT INTO audit_log (action) VALUES ('test.entry')"))
    for statement in ("UPDATE audit_log SET action = 'x'", "DELETE FROM audit_log", "TRUNCATE audit_log"):
        with pytest.raises(DBAPIError, match="append-only"):
            async with app.state.sessionmaker() as session, session.begin():
                await session.execute(text(statement))
