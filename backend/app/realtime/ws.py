"""WS /ws/auctions/{id}: a snapshot on connect, then every committed change."""

import asyncio
import contextlib
import logging

from fastapi import APIRouter, WebSocket

from app.realtime.broker import RESYNC, channel_for
from app.views import load_auction_public

logger = logging.getLogger("adal.realtime")
router = APIRouter()

CLOSE_POLICY = 1008
CLOSE_NOT_FOUND = 4404


@router.websocket("/ws/auctions/{auction_id}")
async def auction_socket(websocket: WebSocket, auction_id: int) -> None:
    app = websocket.app
    origin = websocket.headers.get("origin")
    # Browsers always send Origin on WebSockets; refuse pages from other sites.
    if origin is not None and origin.rstrip("/") not in app.state.settings.allowed_origins:
        await websocket.close(code=CLOSE_POLICY)
        return

    async def snapshot() -> dict | None:
        async with app.state.sessionmaker() as session:
            return await load_auction_public(session, app.state.strategies, auction_id)

    # Subscribe before reading the snapshot so no event can fall in between.
    async with app.state.broker.subscribe(channel_for(auction_id)) as queue:
        first = await snapshot()
        if first is None:
            await websocket.close(code=CLOSE_NOT_FOUND)
            return
        await websocket.accept()
        await websocket.send_json({"type": "snapshot", "auction": first})

        async def forward() -> None:
            while True:
                message = await queue.get()
                if message == RESYNC:
                    fresh = await snapshot()
                    if fresh is None:
                        return
                    message = {"type": "snapshot", "auction": fresh}
                await websocket.send_json(message)

        forwarder = asyncio.create_task(forward())
        try:
            while True:
                incoming = await websocket.receive()  # clients send nothing; this only watches for the close
                if incoming["type"] == "websocket.disconnect":
                    break
        finally:
            forwarder.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await forwarder
