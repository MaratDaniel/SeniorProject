"""Listings and photos: upload checks, creation, editing, scheduling and withdrawal (FR-7, FR-8, FR-11, FR-39, DR-8)."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio
JPEG = b"\xff\xd8\xff" + b"\0" * 64  # the API trusts the first bytes, not the file name


async def upload(client: AsyncClient, account, data: bytes = JPEG, name: str = "photo.jpg"):  # type: ignore[no-untyped-def]
    return await client.post("/api/uploads/images", headers=account.headers, files={"file": (name, data, "image/jpeg")})


async def listing(client: AsyncClient, seller, **fields):  # type: ignore[no-untyped-def]
    body = {"title": "Table lamp", "category": "home", "starting_price": "60.00"} | fields
    return await client.post("/api/listings", headers=seller.headers, json=body)


async def auction(client: AsyncClient, seller, listing_id: int, starts_in: timedelta = timedelta(0), runs: timedelta = timedelta(hours=1), **fields):  # type: ignore[no-untyped-def]
    starts = datetime.now(UTC) + starts_in
    body = {"format": "english", "starts_at": starts.isoformat(), "ends_at": (starts + runs).isoformat(), "min_increment": "5.00"} | fields
    return await client.post(f"/api/listings/{listing_id}/auction", headers=seller.headers, json=body)


def code(response) -> tuple[int, str]:  # type: ignore[no-untyped-def]
    return response.status_code, response.json()["error"]["code"]


async def test_photos_are_checked_by_content_and_size(client: AsyncClient, accounts) -> None:  # type: ignore[no-untyped-def]
    seller, buyer = await accounts("seller"), await accounts("buyer")
    assert code(await upload(client, seller, b"<html>not a photo</html>")) == (400, "unsupported_image")
    assert code(await upload(client, seller, b"GIF89a" + b"\0" * 64, "photo.gif")) == (400, "unsupported_image")
    assert code(await upload(client, seller, b"\xff\xd8\xff" + b"\0" * (5 * 1024 * 1024 + 1))) == (413, "image_too_large")
    assert code(await upload(client, buyer)) == (403, "forbidden")  # only sellers upload

    stored = await upload(client, seller, name="../../etc/passwd.jpg")
    assert stored.status_code == 201
    assert stored.json()["url"].startswith("/media/") and "passwd" not in stored.json()["url"]  # a random name, never the client's


async def test_a_listing_is_validated_and_its_reserve_stays_hidden(client: AsyncClient, accounts) -> None:  # type: ignore[no-untyped-def]
    seller, other = await accounts("seller"), await accounts("seller")
    mine = (await upload(client, seller)).json()["id"]
    theirs = (await upload(client, other)).json()["id"]

    assert code(await listing(client, seller, category="weapons")) == (422, "validation_error")
    assert code(await listing(client, seller, reserve_price="10.00")) == (422, "validation_error")  # below the starting price
    assert code(await listing(client, seller, starting_price="0")) == (422, "validation_error")
    assert code(await listing(client, seller, image_ids=[theirs])) == (422, "validation_error")  # another seller's photo
    assert code(await listing(client, seller, seller_id=other.id)) == (422, "validation_error")  # unknown fields are not bound

    created = await listing(client, seller, reserve_price="90.00", image_ids=[mine])
    assert created.status_code == 201 and created.json()["reserve_price"] == "90.00"
    listing_id = created.json()["id"]
    for viewer in ({}, other.headers):
        assert (await client.get(f"/api/listings/{listing_id}", headers=viewer)).json()["reserve_price"] is None  # FR-39


async def test_only_the_owner_edits_and_prices_lock_after_the_first_bid(client: AsyncClient, accounts) -> None:  # type: ignore[no-untyped-def]
    seller, other, buyer = await accounts("seller"), await accounts("seller"), await accounts("buyer")
    first, second = [(await upload(client, seller)).json()["id"] for _ in range(2)]
    listing_id = (await listing(client, seller, image_ids=[first, second])).json()["id"]
    url = f"/api/listings/{listing_id}"

    assert code(await client.patch(url, headers=other.headers, json={"title": "Hijacked"})) == (403, "forbidden")
    edited = await client.patch(url, headers=seller.headers, json={"title": "Lamp with linen shade", "starting_price": "65.00", "image_ids": [second, first]})
    assert edited.status_code == 200
    assert (edited.json()["title"], edited.json()["starting_price"]) == ("Lamp with linen shade", "65.00")
    assert [image["id"] for image in edited.json()["images"]] == [second, first]  # the first photo is the cover
    assert code(await client.patch(url, headers=seller.headers, json={"reserve_price": "1.00"})) == (422, "validation_error")

    auction_id = (await auction(client, seller, listing_id)).json()["id"]
    assert (await client.post(f"/api/auctions/{auction_id}/bids", headers=buyer.headers, json={"amount": "65.00"})).status_code == 201
    assert code(await client.patch(url, headers=seller.headers, json={"starting_price": "1.00"})) == (409, "listing_locked")  # FR-8
    assert (await client.patch(url, headers=seller.headers, json={"description": "Small chip on the base."})).status_code == 200


async def test_an_auction_needs_a_sensible_schedule(client: AsyncClient, accounts) -> None:  # type: ignore[no-untyped-def]
    seller, other, buyer = await accounts("seller"), await accounts("seller"), await accounts("buyer")
    listing_id = (await listing(client, seller)).json()["id"]

    assert code(await client.post(f"/api/listings/{listing_id}/auction", headers=other.headers, json={})) == (422, "validation_error")
    assert code(await auction(client, other, listing_id)) == (403, "forbidden")
    assert code(await auction(client, seller, listing_id, starts_in=timedelta(hours=-1))) == (400, "invalid_schedule")
    assert code(await auction(client, seller, listing_id, runs=timedelta(minutes=2))) == (400, "invalid_schedule")
    assert code(await auction(client, seller, listing_id, runs=timedelta(days=31))) == (400, "invalid_schedule")
    assert code(await auction(client, seller, listing_id, runs=timedelta(hours=-1))) == (400, "invalid_schedule")
    assert code(await auction(client, seller, listing_id, format="vickrey")) == (400, "format_unavailable")  # spring 2027
    assert code(await auction(client, seller, listing_id, min_increment="0")) == (422, "validation_error")

    scheduled = await auction(client, seller, listing_id, starts_in=timedelta(hours=1))
    assert scheduled.status_code == 201 and scheduled.json()["status"] == "scheduled"
    assert code(await auction(client, seller, listing_id)) == (409, "auction_exists")  # one auction per listing
    early = await client.post(f"/api/auctions/{scheduled.json()['id']}/bids", headers=buyer.headers, json={"amount": "60.00"})
    assert code(early) == (409, "auction_not_started")


async def test_withdrawing_cancels_the_auction_unless_it_has_a_bid(client: AsyncClient, accounts) -> None:  # type: ignore[no-untyped-def]
    seller, other, buyer = await accounts("seller"), await accounts("seller"), await accounts("buyer")
    listing_id = (await listing(client, seller, title="Withdrawn lamp")).json()["id"]
    auction_id = (await auction(client, seller, listing_id, starts_in=timedelta(hours=1))).json()["id"]

    assert code(await client.delete(f"/api/listings/{listing_id}", headers=other.headers)) == (403, "forbidden")
    assert (await client.delete(f"/api/listings/{listing_id}", headers=seller.headers)).status_code == 204
    cancelled = (await client.get(f"/api/auctions/{auction_id}")).json()
    assert cancelled["status"] == "cancelled" and cancelled["closed_at"] is not None
    assert code(await client.post(f"/api/auctions/{auction_id}/bids", headers=buyer.headers, json={"amount": "60.00"})) == (409, "auction_cancelled")
    browse = (await client.get("/api/auctions", params={"q": "Withdrawn lamp"})).json()
    assert browse["total"] == 0  # cancelled auctions leave the catalogue

    # A bid is a binding offer (DR-8): once there is one, the seller cannot withdraw.
    live_listing = (await listing(client, seller)).json()["id"]
    live = (await auction(client, seller, live_listing)).json()["id"]
    assert (await client.post(f"/api/auctions/{live}/bids", headers=buyer.headers, json={"amount": "60.00"})).status_code == 201
    assert code(await client.delete(f"/api/listings/{live_listing}", headers=seller.headers)) == (409, "has_bids")
