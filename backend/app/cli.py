"""Developer commands.

    python -m app.cli init-env       write backend/.env with fresh secrets for local development
    python -m app.cli create-admin   create an administrator account (prompts for the password)
    python -m app.cli seed-demo      demo users and auctions; credentials go to .demo-accounts.txt
                                     (--accounts-file PATH puts them elsewhere, - prints them)
    python -m app.cli close-in ID    demo helper: make live auction ID end in 30 seconds (--seconds N)
"""

import argparse
import asyncio
import getpass
import os
import secrets
import shutil
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy import select

from app import audit
from app.config import Settings, get_settings
from app.db import db_now, make_engine, make_sessionmaker
from app.engine.registry import default_registry
from app.engine.service import lock_auction, place_bid
from app.models import Auction, AuctionStatus, Listing, ListingImage, Role, User
from app.realtime.broker import RedisBroker, channel_for
from app.security.passwords import hash_password
from app.security.totp import SecretBox, new_secret

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEMO_IMAGES = BACKEND_DIR / "demo" / "img"
DEMO_ACCOUNTS = BACKEND_DIR / ".demo-accounts.txt"


def init_env(_: argparse.Namespace) -> int:
    target = BACKEND_DIR / ".env"
    if target.exists():
        print(f"{target} already exists; not overwriting it.")
        return 1
    content = "\n".join(
        [
            "# Local development settings. Never commit this file.",
            "ADAL_ENV=dev",
            "ADAL_DATABASE_URL=postgresql+asyncpg://adal@127.0.0.1:54329/adal",
            f"ADAL_JWT_SECRET={secrets.token_urlsafe(48)}",
            f"ADAL_MFA_ENCRYPTION_KEY={Fernet.generate_key().decode()}",
            "ADAL_FRONTEND_URL=http://localhost:5173",
            "ADAL_COOKIE_SECURE=false",
            "ADAL_MEDIA_DIR=media",
            "",
        ]
    )
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(content)
    print(f"Wrote {target} (readable only by you).")
    return 0


async def _create_admin(email: str, password: str) -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    try:
        async with make_sessionmaker(engine)() as session, session.begin():
            if await session.scalar(select(User.id).where(User.email == email)):
                raise SystemExit(f"{email} already has an account.")
            session.add(
                User(email=email, password_hash=await hash_password(password), role=Role.ADMIN, email_verified_at=await db_now(session))
            )
    finally:
        await engine.dispose()


def create_admin(args: argparse.Namespace) -> int:
    email = args.email.strip().lower()
    password = getpass.getpass("Password (10+ characters): ")
    if len(password) < 10:
        print("The password must have at least 10 characters.")
        return 1
    asyncio.run(_create_admin(email, password))
    print(f"Created administrator {email}. Sign in and turn on two-step sign-in before using admin pages.")
    return 0


DEMO_LOTS = [
    # (image, title, category, description, starting, reserve, step, opens in, runs for)
    # Sample items for the demo. The pictures are illustrations, not photographs of real objects.
    ("clock.jpg", "Brass mantel clock", "antiques",
     "A sample item for the demo: a brass-cased mantel clock with a white enamel dial. The picture is an illustration.",
     "90.00", "120.00", "5.00", timedelta(hours=-1), timedelta(minutes=58)),
    ("lamp.jpg", "Table lamp with linen shade", "home",
     "A sample item for the demo: a black-stemmed table lamp with a pleated linen shade. The picture is an illustration.",
     "60.00", None, "5.00", timedelta(minutes=-40), timedelta(hours=2)),
    ("painting.jpg", "Hills at dusk, oil on canvas", "art",
     "A sample item for the demo: a landscape in oils in a gilt frame. The picture is an illustration.",
     "150.00", "200.00", "10.00", timedelta(hours=-3), timedelta(days=1)),
    ("chair.jpg", "Oak side chair", "furniture",
     "A sample item for the demo: a carved oak chair with a woven back panel. The picture is an illustration.",
     "110.00", None, "5.00", timedelta(hours=-2), timedelta(days=2)),
    ("vase.jpg", "Glazed ceramic vase", "home",
     "A sample item for the demo: a pale green glazed vase with a brass-coloured wave pattern. The picture is an illustration.",
     "45.00", None, "5.00", timedelta(hours=-5), timedelta(days=3)),
    ("trunk.jpg", "Leather travel trunk", "fashion",
     "A sample item for the demo: a brown leather trunk with brass fittings. The picture is an illustration.",
     "130.00", "180.00", "10.00", timedelta(hours=6), timedelta(days=2)),
    ("camera.jpg", "Rangefinder camera", "electronics",
     "A sample item for the demo: a compact film camera with a green leatherette body. The picture is an illustration.",
     "75.00", None, "5.00", timedelta(days=1), timedelta(days=3)),
    ("textile.jpg", "Woven wall rug", "collectibles",
     "A sample item for the demo: a hand-woven rug with a diamond motif and fringed edges. The picture is an illustration.",
     "100.00", None, "5.00", timedelta(days=2), timedelta(days=4)),
]


async def _seed_demo() -> list[str]:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    sessionmaker = make_sessionmaker(engine)
    registry = default_registry(settings)
    box = SecretBox(settings.mfa_encryption_key.get_secret_value())
    media = Path(settings.media_dir)
    media.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    try:
        async with sessionmaker() as session, session.begin():
            if await session.scalar(select(User.id).where(User.email == "seller@example.com")):
                raise SystemExit("Demo data is already there. Reset the database to seed again.")
            now = await db_now(session)
            people: dict[str, User] = {}
            for key, email, role in [
                ("seller", "seller@example.com", Role.SELLER),
                ("buyer1", "buyer1@example.com", Role.BUYER),
                ("buyer2", "buyer2@example.com", Role.BUYER),
            ]:
                password = secrets.token_urlsafe(12)
                secret = new_secret()
                user = User(
                    email=email,
                    password_hash=await hash_password(password),
                    role=role,
                    email_verified_at=now,
                    mfa_enabled=True,
                    mfa_secret_enc=box.seal(secret),
                )
                session.add(user)
                people[key] = user
                lines.append(f"{role:<6} {email:<22} password: {password}   TOTP secret: {secret}")
            await session.flush()

            for image, title, category, description, starting, reserve, step, opens, runs in DEMO_LOTS:
                listing = Listing(
                    seller_id=people["seller"].id,
                    title=title,
                    category=category,
                    description=description,
                    starting_price=Decimal(starting),
                    reserve_price=Decimal(reserve) if reserve else None,
                )
                session.add(listing)
                await session.flush()
                source = DEMO_IMAGES / image
                key = f"{secrets.token_urlsafe(18)}{source.suffix}"
                shutil.copyfile(source, media / key)
                session.add(
                    ListingImage(
                        uploader_id=people["seller"].id,
                        listing_id=listing.id,
                        storage_key=key,
                        content_type="image/jpeg",
                        size_bytes=source.stat().st_size,
                    )
                )
                starts = now + opens
                session.add(
                    Auction(
                        listing_id=listing.id,
                        format="english",
                        status=AuctionStatus.ACTIVE if starts <= now else AuctionStatus.SCHEDULED,
                        starts_at=starts,
                        ends_at=now + runs,
                        original_ends_at=now + runs,
                        min_increment=Decimal(step),
                    )
                )
        # Opening bids go through the engine so they follow every rule.
        async with sessionmaker() as session:
            auctions = list(
                await session.scalars(select(Auction).where(Auction.status == AuctionStatus.ACTIVE).order_by(Auction.id).limit(2))
            )
        for auction, amounts in zip(auctions, [["90.00", "95.00", "105.00"], ["60.00"]], strict=False):
            for index, amount in enumerate(amounts):
                bidder = people["buyer1"] if index % 2 == 0 else people["buyer2"]
                async with sessionmaker() as session, session.begin():
                    await place_bid(session, registry, auction_id=auction.id, bidder=bidder, amount=Decimal(amount))
    finally:
        await engine.dispose()
    return lines


def _can_write(path: Path) -> bool:
    return os.access(path, os.W_OK) if path.exists() else os.access(path.parent, os.W_OK)


def seed_demo(args: argparse.Namespace) -> int:
    # The passwords exist only in this output, so check where it goes before touching the database.
    # In the Docker image the app user cannot write to /app: use --accounts-file - there.
    target = None if args.accounts_file == "-" else Path(args.accounts_file)
    if target is not None and not _can_write(target):
        print(f"Cannot write {target}. Pass --accounts-file with a writable path, or - to print the accounts.", file=sys.stderr)
        return 1
    lines = asyncio.run(_seed_demo())
    text = "# Demo accounts for local development only. Add each TOTP secret to an authenticator app.\n" + "\n".join(lines) + "\n"
    if target is None:
        sys.stdout.write(text)
        print(f"Seeded 3 demo accounts and {len(DEMO_LOTS)} auctions.", file=sys.stderr)
        return 0
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(text)
    print(f"Seeded 3 demo accounts and {len(DEMO_LOTS)} auctions. Credentials: {target}")
    return 0


async def _close_in(settings: Settings, auction_id: int, seconds: int) -> None:
    """Move a live auction's end to a few seconds from now, so a demo can show the close without waiting."""
    if settings.env != "dev":
        raise SystemExit("close-in is a demo helper: it only runs with ADAL_ENV=dev.")
    if seconds < 1:
        raise SystemExit("--seconds must be at least 1.")
    engine = make_engine(settings.database_url)
    try:
        async with make_sessionmaker(engine)() as session, session.begin():
            auction = await lock_auction(session, auction_id)  # the same lock a bid and the close take
            if auction is None or auction.status != AuctionStatus.ACTIVE:
                raise SystemExit(f"Auction {auction_id} is not live.")
            auction.ends_at = await db_now(session) + timedelta(seconds=seconds)
            auction.original_ends_at = min(auction.original_ends_at, auction.ends_at)
            audit.record(session, "auction.end_moved", target_type="auction", target_id=auction_id, data={"seconds": seconds})
            ends_at = auction.ends_at
    finally:
        await engine.dispose()
    if settings.redis_url:  # open auction pages follow the new end at once; without Redis they pick it up on reload
        broker = RedisBroker(settings.redis_url)
        await broker.start()
        try:
            event = {"type": "time_extended", "auction_id": auction_id, "ends_at": ends_at.isoformat().replace("+00:00", "Z")}
            await broker.publish(channel_for(auction_id), event)
        finally:
            await broker.stop()


def close_in(args: argparse.Namespace) -> int:
    asyncio.run(_close_in(get_settings(), args.auction_id, args.seconds))
    print(f"Auction {args.auction_id} now ends in {args.seconds} seconds. Reload its page to see the new end.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-env").set_defaults(func=init_env)
    admin = commands.add_parser("create-admin")
    admin.add_argument("--email", required=True)
    admin.set_defaults(func=create_admin)
    seed = commands.add_parser("seed-demo")
    seed.add_argument(
        "--accounts-file",
        default=str(DEMO_ACCOUNTS),
        help="where to write the demo credentials (default: backend/.demo-accounts.txt); - prints them",
    )
    seed.set_defaults(func=seed_demo)
    soon = commands.add_parser("close-in")
    soon.add_argument("auction_id", type=int)
    soon.add_argument("--seconds", type=int, default=30)
    soon.set_defaults(func=close_in)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
