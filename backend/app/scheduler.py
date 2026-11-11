"""Opens scheduled auctions, closes ended ones and expires unpaid sales.

Every step is idempotent and takes the same row locks as bidding, so running it
in several processes at once is safe (UC-7, NFR-9: after a restart the next tick
catches up on anything that ended while the server was down).
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import audit
from app.config import Settings
from app.engine.base import StrategyRegistry
from app.engine.service import close_auction
from app.models import OPEN_STATUSES, Auction, AuctionStatus, Transaction, TransactionStatus
from app.realtime.broker import Broker, channel_for

logger = logging.getLogger("adal.scheduler")
BATCH = 100


@dataclass
class Scheduler:
    sessionmaker: async_sessionmaker[AsyncSession]
    broker: Broker
    strategies: StrategyRegistry
    settings: Settings

    async def tick(self) -> None:
        await self.open_due()
        await self.close_due()
        await self.expire_due()

    async def open_due(self) -> list[int]:
        async with self.sessionmaker() as session, session.begin():
            ids = list(
                await session.scalars(
                    update(Auction)
                    .where(Auction.status == AuctionStatus.SCHEDULED, Auction.starts_at <= func.clock_timestamp())
                    .values(status=AuctionStatus.ACTIVE)
                    .returning(Auction.id)
                )
            )
        for auction_id in ids:
            await self.broker.publish(
                channel_for(auction_id), {"type": "status_changed", "auction_id": auction_id, "status": AuctionStatus.ACTIVE.value}
            )
        return ids

    async def close_due(self) -> list[int]:
        async with self.sessionmaker() as session:
            due = list(
                await session.scalars(
                    select(Auction.id)
                    .where(Auction.status.in_(OPEN_STATUSES), Auction.ends_at <= func.clock_timestamp())
                    .order_by(Auction.ends_at)
                    .limit(BATCH)
                )
            )
        closed: list[int] = []
        for auction_id in due:
            async with self.sessionmaker() as session, session.begin():
                events = await close_auction(
                    session,
                    self.strategies,
                    auction_id,
                    transaction_expiry=timedelta(hours=self.settings.transaction_expiry_hours),
                    frontend_url=self.settings.frontend_url,
                )
            for event in events:  # published only after the commit
                await self.broker.publish(channel_for(auction_id), event)
            if events:
                closed.append(auction_id)
        return closed

    async def expire_due(self) -> list[int]:
        async with self.sessionmaker() as session, session.begin():
            rows = (
                await session.execute(
                    update(Transaction)
                    .where(Transaction.status == TransactionStatus.PENDING, Transaction.expires_at <= func.clock_timestamp())
                    .values(status=TransactionStatus.EXPIRED)
                    .returning(Transaction.id, Transaction.auction_id)
                )
            ).all()
            for tx_id, auction_id in rows:
                audit.record(session, "transaction.expired", target_type="transaction", target_id=tx_id, data={"auction_id": auction_id})
        return [tx_id for tx_id, _ in rows]

    async def run_forever(self) -> None:
        logger.info("scheduler started (every %.1fs)", self.settings.scheduler_interval_seconds)
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("scheduler tick failed")
            await asyncio.sleep(self.settings.scheduler_interval_seconds)
