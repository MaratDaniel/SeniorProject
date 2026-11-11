"""Fan-out of auction events to WebSocket watchers.

InMemoryBroker works inside one process. RedisBroker publishes through Redis so
events reach watchers connected to any API process; each process keeps a single
Redis subscription and fans out locally.
"""

import asyncio
import contextlib
import json
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any, Protocol

import redis.asyncio as redis

logger = logging.getLogger("adal.realtime")

CHANNEL_PREFIX = "adal:auction:"
QUEUE_SIZE = 256
RESYNC = {"type": "_resync"}  # internal: the watcher fell behind and needs a fresh snapshot


def channel_for(auction_id: int) -> str:
    return f"{CHANNEL_PREFIX}{auction_id}"


class Broker(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def publish(self, channel: str, message: dict[str, Any]) -> None: ...
    def subscribe(self, channel: str) -> contextlib.AbstractAsyncContextManager[asyncio.Queue[dict[str, Any]]]: ...


class LocalFanout:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    def deliver(self, channel: str, message: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(channel, ())):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # A slow watcher: drop its backlog and make it reload the whole state.
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(RESYNC)

    @contextlib.asynccontextmanager
    async def subscribe(self, channel: str) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._subscribers[channel].add(queue)
        try:
            yield queue
        finally:
            subscribers = self._subscribers.get(channel)
            if subscribers is not None:
                subscribers.discard(queue)
                if not subscribers:
                    del self._subscribers[channel]


class InMemoryBroker:
    def __init__(self) -> None:
        self._local = LocalFanout()

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        self._local.deliver(channel, message)

    def subscribe(self, channel: str) -> contextlib.AbstractAsyncContextManager[asyncio.Queue[dict[str, Any]]]:
        return self._local.subscribe(channel)


class RedisBroker:
    def __init__(self, url: str) -> None:
        self._url = url
        self._local = LocalFanout()
        self._redis: redis.Redis | None = None
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._redis = redis.Redis.from_url(self._url, decode_responses=True)
        await self._redis.ping()
        self._task = asyncio.create_task(self._pump(), name="redis-broker")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._redis is not None:
            await self._redis.aclose()

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        assert self._redis is not None, "broker not started"
        await self._redis.publish(channel, json.dumps(message))

    def subscribe(self, channel: str) -> contextlib.AbstractAsyncContextManager[asyncio.Queue[dict[str, Any]]]:
        return self._local.subscribe(channel)

    async def _pump(self) -> None:
        assert self._redis is not None
        while True:
            pubsub = self._redis.pubsub()
            try:
                await pubsub.psubscribe(f"{CHANNEL_PREFIX}*")
                async for message in pubsub.listen():
                    if message.get("type") != "pmessage":
                        continue
                    try:
                        payload = json.loads(message["data"])
                    except (TypeError, ValueError):
                        logger.warning("dropping a malformed event")
                        continue
                    self._local.deliver(message["channel"], payload)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("redis subscription failed; reconnecting")
                await asyncio.sleep(1)
            finally:
                with contextlib.suppress(Exception):
                    await pubsub.aclose()
