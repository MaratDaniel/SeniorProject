"""Database engine and sessions."""

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def make_engine(url: str) -> AsyncEngine:
    return create_async_engine(
        url,
        pool_size=20,
        max_overflow=20,
        pool_pre_ping=True,
        connect_args={
            # A bid waiting on a busy auction row gives up after 5 s instead of holding a
            # pooled connection forever; the API turns that into 503 "busy".
            "server_settings": {"timezone": "UTC", "lock_timeout": "5s", "statement_timeout": "15s"},
        },
    )


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def db_now(session: AsyncSession) -> datetime:
    """The database clock: the one time authority for bids and closing (DR-1)."""
    return (await session.execute(text("SELECT clock_timestamp()"))).scalar_one()
