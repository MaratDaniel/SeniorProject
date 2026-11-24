"""A listing has a currency: US dollars unless the seller chooses another."""

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient

from tests.conftest import Account, make_auction

pytestmark = pytest.mark.anyio

LISTING = {"title": "Oak side chair", "description": "", "category": "antiques", "starting_price": "110.00"}


async def test_a_new_listing_is_in_us_dollars_by_default(client: AsyncClient, accounts: Callable[..., Awaitable[Account]]) -> None:
    seller = await accounts("seller")
    res = await client.post("/api/listings", json=LISTING, headers=seller.headers)
    assert res.status_code == 201, res.text
    assert res.json()["currency"] == "USD"


async def test_the_seller_can_choose_another_currency(client: AsyncClient, accounts: Callable[..., Awaitable[Account]]) -> None:
    seller = await accounts("seller")
    res = await client.post("/api/listings", json={**LISTING, "currency": "EUR"}, headers=seller.headers)
    assert res.status_code == 201
    assert res.json()["currency"] == "EUR"


async def test_an_unknown_currency_is_refused(client: AsyncClient, accounts: Callable[..., Awaitable[Account]]) -> None:
    seller = await accounts("seller")
    res = await client.post("/api/listings", json={**LISTING, "currency": "XYZ"}, headers=seller.headers)
    assert res.status_code == 422


async def test_auctions_show_their_listing_currency(client: AsyncClient, app, accounts: Callable[..., Awaitable[Account]]) -> None:  # type: ignore[no-untyped-def]
    seller = await accounts("seller")
    auction_id = await make_auction(app, seller)
    res = await client.get(f"/api/auctions/{auction_id}")
    assert res.status_code == 200
    assert res.json()["currency"] == "USD"
