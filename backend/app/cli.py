"""Developer commands.

    python -m app.cli init-env       write backend/.env with fresh secrets for local development
    python -m app.cli create-admin   create an administrator account (prompts for the password)
    python -m app.cli seed-demo      demo users and auctions; credentials go to .demo-accounts.txt
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

from app.config import get_settings
from app.db import db_now, make_engine, make_sessionmaker
from app.engine.registry import default_registry
from app.engine.service import place_bid
from app.models import Auction, AuctionStatus, Listing, ListingImage, Role, User
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
    ("scales.jpg", "Box of brass weights with small balance", "antiques",
     "An oak case holding a folding hand balance and a set of stamped brass weights. Cleveland Museum of Art, public domain.",
     "200.00", "250.00", "5.00", timedelta(hours=-1), timedelta(hours=3)),
    ("balance.jpg", "Brass pedestal balance", "antiques",
     "A gilded brass beam balance on a fluted column and a white marble base. The Metropolitan Museum of Art, public domain.",
     "120.00", None, "5.00", timedelta(minutes=-50), timedelta(minutes=58)),
    ("beam.jpg", "Beam balance, 16th century", "collectibles",
     "An early beam balance with hanging pans. The Metropolitan Museum of Art, public domain.",
     "300.00", "400.00", "10.00", timedelta(hours=-2), timedelta(days=2)),
    ("auction-room.jpg", "Christie's Auction Room, print, 1808", "art",
     "Hand-coloured aquatint of a London sale room. The Metropolitan Museum of Art, public domain.",
     "80.00", None, "2.00", timedelta(days=1), timedelta(days=1, hours=6)),
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
        for auction, amounts in zip(auctions, [["200.00", "210.00", "225.00"], ["120.00"]], strict=False):
            for index, amount in enumerate(amounts):
                bidder = people["buyer1"] if index % 2 == 0 else people["buyer2"]
                async with sessionmaker() as session, session.begin():
                    await place_bid(session, registry, auction_id=auction.id, bidder=bidder, amount=Decimal(amount))
    finally:
        await engine.dispose()
    return lines


def seed_demo(_: argparse.Namespace) -> int:
    lines = asyncio.run(_seed_demo())
    fd = os.open(DEMO_ACCOUNTS, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write("# Demo accounts for local development only. Add each TOTP secret to an authenticator app.\n")
        handle.write("\n".join(lines) + "\n")
    print(f"Seeded 3 demo accounts and 4 auctions. Credentials: {DEMO_ACCOUNTS}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-env").set_defaults(func=init_env)
    admin = commands.add_parser("create-admin")
    admin.add_argument("--email", required=True)
    admin.set_defaults(func=create_admin)
    commands.add_parser("seed-demo").set_defaults(func=seed_demo)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
