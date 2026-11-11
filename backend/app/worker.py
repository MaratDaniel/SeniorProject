"""Standalone scheduler process: `python -m app.worker`.

Run it next to API processes started with ADAL_SCHEDULER_ENABLED=false and a shared
ADAL_REDIS_URL, so events it publishes reach every watcher.
"""

import asyncio
import logging

from app.config import get_settings
from app.db import make_engine, make_sessionmaker
from app.engine.registry import default_registry
from app.realtime.broker import Broker, InMemoryBroker, RedisBroker
from app.scheduler import Scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    broker: Broker = RedisBroker(settings.redis_url) if settings.redis_url else InMemoryBroker()
    if not settings.redis_url:
        logging.getLogger("adal.worker").warning("ADAL_REDIS_URL is not set: events will not reach API processes")
    await broker.start()
    try:
        await Scheduler(make_sessionmaker(engine), broker, default_registry(settings), settings).run_forever()
    finally:
        await broker.stop()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
