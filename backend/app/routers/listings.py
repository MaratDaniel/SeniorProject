"""Listings, photos and auction setup (FR-7 to FR-13, FR-39)."""

import os
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Request, Response, UploadFile
from sqlalchemy import or_, select, true, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app import audit
from app.db import db_now
from app.deps import BrokerDep, LimiterDep, OptionalUser, SellerUser, SessionDep, SettingsDep, StrategiesDep, client_ip
from app.engine.service import lock_auction
from app.errors import ApiError, field_error, forbidden, not_found
from app.models import OPEN_STATUSES, Auction, AuctionStatus, Listing, ListingImage, ListingStatus, User
from app.realtime.broker import channel_for
from app.schemas import (
    AuctionCreateIn,
    AuctionDetailOut,
    CategoryOut,
    ImageOut,
    ListingCreateIn,
    ListingOut,
    ListingUpdateIn,
)
from app.views import load_auction_detail, load_listing, media_url

router = APIRouter(prefix="/api", tags=["listings"])

CATEGORIES: dict[str, str] = {
    "art": "Art",
    "antiques": "Antiques",
    "collectibles": "Collectibles",
    "books": "Books",
    "electronics": "Electronics",
    "fashion": "Fashion",
    "home": "Home and garden",
    "other": "Other",
}
MIN_DURATION = timedelta(minutes=5)
MAX_DURATION = timedelta(days=30)
START_SLACK = timedelta(minutes=1)
PRICE_FIELDS = {"starting_price", "reserve_price"}


def _image_kind(data: bytes) -> tuple[str, str] | None:
    """Trust the bytes, not the filename or the client's content type."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    return None


def _write_new_file(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)  # never overwrite
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)


async def _attach_images(session: AsyncSession, listing: Listing, owner: User, image_ids: list[int]) -> None:
    if len(set(image_ids)) != len(image_ids):
        raise field_error("image_ids", "A photo is listed twice.")
    # Detach photos that are no longer in the list.
    await session.execute(
        update(ListingImage)
        .where(ListingImage.listing_id == listing.id, ListingImage.id.not_in(image_ids) if image_ids else true())
        .values(listing_id=None)
    )
    for position, image_id in enumerate(image_ids):
        result = await session.execute(
            update(ListingImage)
            .where(
                ListingImage.id == image_id,
                ListingImage.uploader_id == owner.id,  # only your own uploads
                or_(ListingImage.listing_id.is_(None), ListingImage.listing_id == listing.id),
            )
            .values(listing_id=listing.id, position=position)
        )
        if result.rowcount != 1:
            raise field_error("image_ids", "One of the photos was not found. Upload it again.")


def _check_prices(starting, reserve) -> None:  # type: ignore[no-untyped-def]
    if reserve is not None and reserve < starting:
        raise field_error("reserve_price", "The reserve price cannot be lower than the starting price.")


async def _owned_listing(session: AsyncSession, listing_id: int, user: User) -> Listing:
    listing = (
        await session.execute(
            select(Listing).where(Listing.id == listing_id).with_for_update().execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if listing is None:
        raise not_found("This listing does not exist.")
    if listing.seller_id != user.id:
        raise forbidden("This is not your listing.")
    return listing


@router.get("/categories", response_model=list[CategoryOut])
async def categories() -> list[CategoryOut]:
    return [CategoryOut(slug=slug, name=name) for slug, name in CATEGORIES.items()]


@router.post("/uploads/images", status_code=201, response_model=ImageOut)
async def upload_image(
    request: Request,
    file: Annotated[UploadFile, File()],
    user: SellerUser,
    session: SessionDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> ImageOut:
    limiter.check(f"upload:{user.id}", 30, 600)
    limit = settings.max_upload_bytes
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit + 64 * 1024:
        raise ApiError(413, "image_too_large", "Photos can be at most 5 MB.")
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise ApiError(413, "image_too_large", "Photos can be at most 5 MB.")
    kind = _image_kind(data)
    if kind is None:
        raise ApiError(400, "unsupported_image", "Use a JPEG or PNG photo.")
    extension, content_type = kind
    key = f"{secrets.token_urlsafe(18)}.{extension}"  # random name: no user input reaches the path
    media_root = Path(settings.media_dir)
    await run_in_threadpool(_write_new_file, media_root / key, data)
    async with session.begin():
        image = ListingImage(uploader_id=user.id, storage_key=key, content_type=content_type, size_bytes=len(data))
        session.add(image)
        await session.flush()
        audit.record(session, "image.uploaded", actor_id=user.id, target_type="image", target_id=image.id, ip=client_ip(request))
    return ImageOut(id=image.id, url=media_url(key))


@router.post("/listings", status_code=201, response_model=ListingOut)
async def create_listing(body: ListingCreateIn, request: Request, user: SellerUser, session: SessionDep) -> ListingOut:
    if body.category not in CATEGORIES:
        raise field_error("category", "Choose one of the categories.")
    _check_prices(body.starting_price, body.reserve_price)
    async with session.begin():
        listing = Listing(
            seller_id=user.id,
            title=body.title,
            description=body.description,
            category=body.category,
            starting_price=body.starting_price,
            reserve_price=body.reserve_price,
        )
        session.add(listing)
        await session.flush()
        await _attach_images(session, listing, user, body.image_ids)
        audit.record(session, "listing.created", actor_id=user.id, target_type="listing", target_id=listing.id, ip=client_ip(request))
    out = await load_listing(session, listing.id, viewer=user)
    assert out is not None
    return out


@router.get("/listings/{listing_id}", response_model=ListingOut)
async def get_listing(listing_id: int, viewer: OptionalUser, session: SessionDep) -> ListingOut:
    out = await load_listing(session, listing_id, viewer)
    if out is None:
        raise not_found("This listing does not exist.")
    return out


@router.patch("/listings/{listing_id}", response_model=ListingOut)
async def update_listing(listing_id: int, body: ListingUpdateIn, request: Request, user: SellerUser, session: SessionDep) -> ListingOut:
    changes = body.model_dump(exclude_unset=True)
    async with session.begin():
        listing = await _owned_listing(session, listing_id, user)
        if listing.status != ListingStatus.ACTIVE:
            raise ApiError(409, "listing_locked", "This listing was withdrawn.")
        auction_id = await session.scalar(select(Auction.id).where(Auction.listing_id == listing.id))
        auction = await lock_auction(session, auction_id) if auction_id else None  # serialize with bids
        if PRICE_FIELDS & changes.keys() and auction is not None and auction.bid_count > 0:
            raise ApiError(409, "listing_locked", "Prices cannot change after the first bid.")  # FR-8
        if "category" in changes and changes["category"] not in CATEGORIES:
            raise field_error("category", "Choose one of the categories.")
        for name in ("title", "description", "category", "starting_price", "reserve_price"):  # explicit allowlist
            if name in changes:
                if name in ("title", "description", "category", "starting_price") and changes[name] is None:
                    raise field_error(name, "This field cannot be empty.")
                setattr(listing, name, changes[name])
        _check_prices(listing.starting_price, listing.reserve_price)
        if body.image_ids is not None:
            await _attach_images(session, listing, user, body.image_ids)
        audit.record(
            session, "listing.updated", actor_id=user.id, target_type="listing", target_id=listing.id, ip=client_ip(request), data={"fields": sorted(changes)}
        )
    out = await load_listing(session, listing.id, viewer=user)
    assert out is not None
    return out


@router.delete("/listings/{listing_id}", status_code=204)
async def withdraw_listing(listing_id: int, request: Request, user: SellerUser, session: SessionDep, broker: BrokerDep) -> Response:
    events = []
    async with session.begin():
        listing = await _owned_listing(session, listing_id, user)
        auction_id = await session.scalar(select(Auction.id).where(Auction.listing_id == listing.id))
        auction = await lock_auction(session, auction_id) if auction_id else None
        if auction is not None and auction.bid_count > 0:
            raise ApiError(409, "has_bids", "A listing with bids cannot be withdrawn: a bid is a binding offer.")  # DR-8
        if auction is not None and auction.status in OPEN_STATUSES:
            auction.status = AuctionStatus.CANCELLED
            auction.closed_at = await db_now(session)
            events.append({"type": "status_changed", "auction_id": auction.id, "status": AuctionStatus.CANCELLED.value})
        listing.status = ListingStatus.WITHDRAWN
        audit.record(session, "listing.withdrawn", actor_id=user.id, target_type="listing", target_id=listing.id, ip=client_ip(request))
    for event in events:
        await broker.publish(channel_for(event["auction_id"]), event)
    return Response(status_code=204)


@router.post("/listings/{listing_id}/auction", status_code=201, response_model=AuctionDetailOut)
async def create_auction(
    listing_id: int, body: AuctionCreateIn, request: Request, user: SellerUser, session: SessionDep, strategies: StrategiesDep
) -> AuctionDetailOut:
    if body.format not in strategies:
        raise ApiError(400, "format_unavailable", "This selling format arrives in spring 2027. Use an English auction for now.")
    strategy = strategies.get(body.format)
    try:
        async with session.begin():
            listing = await _owned_listing(session, listing_id, user)
            if listing.status != ListingStatus.ACTIVE:
                raise ApiError(409, "listing_locked", "This listing was withdrawn.")
            if await session.scalar(select(Auction.id).where(Auction.listing_id == listing.id)) is not None:
                raise ApiError(409, "auction_exists", "This listing already has an auction.")
            now = await db_now(session)
            starts_at, ends_at = body.starts_at, body.ends_at
            if starts_at < now - START_SLACK:
                raise ApiError(400, "invalid_schedule", "The opening time is in the past.")
            starts_at = max(starts_at, now)
            if ends_at <= starts_at:
                raise ApiError(400, "invalid_schedule", "The closing time must be after the opening time.")
            if ends_at - starts_at < MIN_DURATION:
                raise ApiError(400, "invalid_schedule", "An auction must run for at least 5 minutes.")
            if ends_at - starts_at > MAX_DURATION:
                raise ApiError(400, "invalid_schedule", "An auction can run for at most 30 days.")
            try:
                strategy.validate_config(
                    starting_price=listing.starting_price, min_increment=body.min_increment, starts_at=starts_at, ends_at=ends_at
                )
            except ValueError as exc:
                raise field_error("min_increment", str(exc)) from exc
            auction = Auction(
                listing_id=listing.id,
                format=body.format,
                status=AuctionStatus.ACTIVE if starts_at <= now else AuctionStatus.SCHEDULED,
                starts_at=starts_at,
                ends_at=ends_at,
                original_ends_at=ends_at,
                min_increment=body.min_increment,
            )
            session.add(auction)
            await session.flush()
            audit.record(
                session,
                "auction.created",
                actor_id=user.id,
                target_type="auction",
                target_id=auction.id,
                ip=client_ip(request),
                data={"format": body.format, "starts_at": starts_at.isoformat(), "ends_at": ends_at.isoformat()},
            )
    except IntegrityError as exc:
        raise ApiError(409, "auction_exists", "This listing already has an auction.") from exc
    out = await load_auction_detail(session, strategies, auction.id, viewer=user)
    assert out is not None
    return out
