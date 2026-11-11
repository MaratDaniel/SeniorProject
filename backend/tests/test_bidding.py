"""Bidding through the API: the shared rules, the English rules and what bidders may see (UC-4, FR-16 to FR-24, FR-39)."""

import pytest
from httpx import AsyncClient

from tests.conftest import make_auction, move_end

pytestmark = pytest.mark.anyio


async def bid(client: AsyncClient, account, auction_id: int, amount: str):  # type: ignore[no-untyped-def]
    return await client.post(f"/api/auctions/{auction_id}/bids", headers=account.headers, json={"amount": amount})


async def test_a_bid_updates_price_leader_and_bidder_numbers(client: AsyncClient, app, accounts) -> None:  # type: ignore[no-untyped-def]
    seller, alice, bob = await accounts("seller"), await accounts("buyer"), await accounts("buyer")
    auction_id = await make_auction(app, seller, starting="100.00", step="5.00", reserve="150.00")

    first = await bid(client, alice, auction_id, "100.00")
    assert first.status_code == 201, first.text
    assert first.json()["bid"]["bidder_number"] == 1
    state = first.json()["auction"]
    assert (state["current_price"], state["min_next_bid"], state["bid_count"], state["reserve_met"]) == ("100.00", "105.00", 1, False)
    assert state["viewer"] == {"is_seller": False, "bidder_number": 1, "is_leader": True, "transaction_id": None}

    second = await bid(client, bob, auction_id, "150.00")
    assert second.json()["bid"]["bidder_number"] == 2 and second.json()["auction"]["reserve_met"] is True

    public = (await client.get(f"/api/auctions/{auction_id}")).json()
    assert public["viewer"] is None and public["leader_bidder_number"] == 2
    assert [b["amount"] for b in public["bids"]] == ["150.00", "100.00"]
    assert "reserve_price" not in public  # the reserve amount never reaches bidders


async def test_shared_and_english_rules_refuse_bad_bids(client: AsyncClient, app, accounts) -> None:  # type: ignore[no-untyped-def]
    seller, alice = await accounts("seller"), await accounts("buyer")
    unverified = await accounts("buyer", verified=False)
    auction_id = await make_auction(app, seller, starting="100.00", step="5.00")

    assert (await bid(client, seller, auction_id, "500.00")).json()["error"]["code"] == "seller_cannot_bid"
    assert (await bid(client, unverified, auction_id, "500.00")).json()["error"]["code"] == "email_not_verified"
    low = await bid(client, alice, auction_id, "99.00")
    assert low.status_code == 409 and low.json()["error"]["details"] == {"min_next_bid": "100.00"}
    assert (await bid(client, alice, auction_id, "100.00")).status_code == 201
    assert (await bid(client, alice, auction_id, "200.00")).json()["error"]["code"] == "already_leading"
    assert (await bid(client, alice, auction_id, "100.001")).status_code == 422  # money has two decimals
    assert (await client.post(f"/api/auctions/{auction_id}/bids", json={"amount": "500.00"})).status_code == 401


async def test_bids_outside_the_window_are_refused(client: AsyncClient, app, accounts) -> None:  # type: ignore[no-untyped-def]
    from datetime import timedelta

    seller, alice = await accounts("seller"), await accounts("buyer")
    upcoming = await make_auction(app, seller, starts_in=timedelta(hours=1), ends_in=timedelta(hours=2))
    assert (await bid(client, alice, upcoming, "100.00")).json()["error"]["code"] == "auction_not_started"

    ended = await make_auction(app, seller)
    await move_end(app, ended, -1)
    assert (await bid(client, alice, ended, "100.00")).json()["error"]["code"] == "auction_ended"


async def test_a_late_bid_extends_the_close(client: AsyncClient, app, accounts) -> None:  # type: ignore[no-untyped-def]
    seller, alice = await accounts("seller"), await accounts("buyer")
    auction_id = await make_auction(app, seller)
    await move_end(app, auction_id, 60)  # one minute left: inside the two-minute window
    before = (await client.get(f"/api/auctions/{auction_id}")).json()["ends_at"]
    after = (await bid(client, alice, auction_id, "100.00")).json()["auction"]["ends_at"]
    assert after > before


async def test_browse_filters_and_searches(client: AsyncClient, app, accounts) -> None:  # type: ignore[no-untyped-def]
    seller = await accounts("seller")
    await make_auction(app, seller)
    page = (await client.get("/api/auctions", params={"q": "brass", "status": "live", "category": "antiques"})).json()
    assert page["total"] >= 1 and all(item["status"] == "active" for item in page["items"])
    assert (await client.get("/api/auctions", params={"q": "%_"})).status_code == 200  # wildcards are escaped
    assert (await client.get("/api/auctions", params={"status": "nonsense"})).status_code == 422
