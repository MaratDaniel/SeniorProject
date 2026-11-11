"""Test setup: a fresh PostgreSQL database migrated with Alembic, and helpers to build users and auctions.

Needs a running PostgreSQL: `tools/devdb.sh start` (or set ADAL_TEST_DATABASE_URL).
"""

import asyncio
import os
import re
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import asyncpg
import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from sqlalchemy import text

from app.config import Settings
from app.db import db_now
from app.main import create_app
from app.models import Auction, AuctionStatus, Listing, User
from app.security.passwords import hash_password
from app.security.tokens import create_access_token
from app.security.totp import SecretBox, code_for_step, current_step, new_secret

BACKEND = Path(__file__).resolve().parent.parent
TEST_DATABASE_URL = os.environ.get("ADAL_TEST_DATABASE_URL", "postgresql+asyncpg://adal@127.0.0.1:54329/adal_test")
PASSWORD = "correct horse battery staple"


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
def database() -> str:
    """Drop and recreate the test database, then run the real migration."""
    plain = TEST_DATABASE_URL.replace("+asyncpg", "")
    server, name = plain.rsplit("/", 1)
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", name):
        raise RuntimeError(f"unexpected test database name: {name!r}")

    async def recreate() -> None:
        connection = await asyncpg.connect(f"{server}/postgres")
        try:
            await connection.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
            await connection.execute(f'CREATE DATABASE "{name}"')
        finally:
            await connection.close()

    asyncio.run(recreate())
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env={**os.environ, "ADAL_DATABASE_URL": TEST_DATABASE_URL},
        check=True,
        capture_output=True,
    )
    return TEST_DATABASE_URL


@pytest.fixture
def settings(tmp_path: Path, database: str) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        env="test",
        database_url=database,
        jwt_secret="t" * 48,
        mfa_encryption_key=Fernet.generate_key().decode(),
        cookie_secure=False,
        scheduler_enabled=False,
        media_dir=str(tmp_path / "media"),
        frontend_url="http://localhost:5173",
    )


@pytest.fixture
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, client=("203.0.113.10", 50000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@dataclass
class Account:
    id: int
    email: str
    role: str
    totp_secret: str | None
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def code(self, offset: int = 0) -> str:
        """A TOTP code for now (+offset steps). Offsets of +-1 are accepted for clock drift."""
        assert self.totp_secret is not None
        return code_for_step(self.totp_secret, current_step() + offset)


async def make_account(app: FastAPI, role: str = "buyer", *, verified: bool = True, mfa: bool = True) -> Account:
    settings: Settings = app.state.settings
    email = f"{role}-{uuid.uuid4().hex[:12]}@example.com"
    secret = new_secret() if mfa else None
    async with app.state.sessionmaker() as session, session.begin():
        now = await db_now(session)
        user = User(
            email=email,
            password_hash=await hash_password(PASSWORD),
            role=role,
            email_verified_at=now if verified else None,
            mfa_enabled=mfa,
            mfa_secret_enc=SecretBox(settings.mfa_encryption_key.get_secret_value()).seal(secret) if secret else None,
        )
        session.add(user)
        await session.flush()
    token = create_access_token(user_id=user.id, role=role, secret=settings.jwt_secret.get_secret_value(), minutes=15)
    return Account(id=user.id, email=email, role=role, totp_secret=secret, token=token)


async def make_auction(
    app: FastAPI,
    seller: Account,
    *,
    starting: str = "100.00",
    step: str = "5.00",
    reserve: str | None = None,
    starts_in: timedelta = timedelta(0),
    ends_in: timedelta = timedelta(hours=1),
) -> int:
    async with app.state.sessionmaker() as session, session.begin():
        now = await db_now(session)
        listing = Listing(
            seller_id=seller.id,
            title="Brass balance",
            description="Test lot",
            category="antiques",
            starting_price=Decimal(starting),
            reserve_price=Decimal(reserve) if reserve else None,
        )
        session.add(listing)
        await session.flush()
        starts_at = now + starts_in
        auction = Auction(
            listing_id=listing.id,
            format="english",
            status=AuctionStatus.ACTIVE if starts_in <= timedelta(0) else AuctionStatus.SCHEDULED,
            starts_at=starts_at if starts_in > timedelta(0) else now - timedelta(seconds=1),
            ends_at=now + ends_in,
            original_ends_at=now + ends_in,
            min_increment=Decimal(step),
        )
        session.add(auction)
        await session.flush()
        return auction.id


async def move_end(app: FastAPI, auction_id: int, seconds_from_now: float) -> None:
    """Move an auction's end time relative to the database clock."""
    async with app.state.sessionmaker() as session, session.begin():
        await session.execute(
            text(
                "UPDATE auctions SET ends_at = clock_timestamp() + make_interval(secs => :s), "
                "starts_at = LEAST(starts_at, clock_timestamp() + make_interval(secs => :s) - interval '1 second') WHERE id = :id"
            ),
            {"s": seconds_from_now, "id": auction_id},
        )


@pytest.fixture
def accounts(app: FastAPI) -> Callable[..., Awaitable[Account]]:
    async def factory(role: str = "buyer", **kwargs: bool) -> Account:
        return await make_account(app, role, **kwargs)

    return factory
