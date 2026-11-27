"""Measure NFR-3 and NFR-4 under load: python -m tools.loadtest (from backend/).

Starts its own API process against the test database. On each of --auctions auctions it opens
--watchers WebSockets and lets --bidders accounts bid against each other at the same time. Reports

  bid time      how long POST /bids takes, request to response (NFR-4: under 300 ms at p95)
  delivery time from the database accepting a bid to each watcher receiving it (NFR-3: under 1 s at p95)

and fails unless every watcher received every accepted bid and every stored result matches.
The full target load of the requirements is --auctions 20 (4,000 open WebSockets).
Needs a running PostgreSQL (tools/devdb.sh start). Nothing is written to the development database.
"""

import argparse
import asyncio
import json
import os
import random
import resource
import secrets
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
from cryptography.fernet import Fernet
from websockets.asyncio.client import connect

from app.db import db_now, make_engine, make_sessionmaker
from app.models import Auction, AuctionStatus, Bid, Listing, User
from app.security.passwords import hash_password
from app.security.tokens import create_access_token

BACKEND = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE = os.environ.get("ADAL_TEST_DATABASE_URL", "postgresql+asyncpg://adal@127.0.0.1:54329/adal_test")
STEP = Decimal("1.00")


def percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(share * (len(ordered) - 1)))]


def summary(name: str, seconds: list[float]) -> dict[str, float | int | str]:
    ms = [s * 1000 for s in seconds]
    return {"what": name, "count": len(ms), "p50_ms": round(statistics.median(ms), 1), "p95_ms": round(percentile(ms, 0.95), 1), "max_ms": round(max(ms), 1)}


async def prepare(database_url: str, jwt_secret: str, bidders: int) -> tuple[int, list[str]]:
    """One live auction with its own verified bidders, written directly so no rate limit or email is involved."""
    engine = make_engine(database_url)
    run = secrets.token_hex(4)
    password_hash = await hash_password(secrets.token_urlsafe(16))
    try:
        async with make_sessionmaker(engine)() as session, session.begin():
            now = await db_now(session)
            people = [
                User(email=f"load-{run}-{i}@example.com", password_hash=password_hash, role="seller" if i == 0 else "buyer", email_verified_at=now)
                for i in range(bidders + 1)
            ]
            session.add_all(people)
            await session.flush()
            listing = Listing(seller_id=people[0].id, title=f"Load test lot {run}", category="other", starting_price=Decimal("100.00"))
            session.add(listing)
            await session.flush()
            auction = Auction(
                listing_id=listing.id, format="english", status=AuctionStatus.ACTIVE, starts_at=now - timedelta(seconds=1),
                ends_at=now + timedelta(hours=6), original_ends_at=now + timedelta(hours=6), min_increment=STEP,
            )
            session.add(auction)
            await session.flush()
            tokens = [create_access_token(user_id=p.id, role=p.role, secret=jwt_secret, minutes=30) for p in people[1:]]
            return auction.id, tokens
    finally:
        await engine.dispose()


async def stored_result(database_url: str, auction_id: int) -> tuple[int, int, Decimal | None]:
    engine = make_engine(database_url)
    try:
        async with make_sessionmaker(engine)() as session:
            auction = await session.get(Auction, auction_id)
            from sqlalchemy import func, select

            rows = await session.scalar(select(func.count()).select_from(Bid).where(Bid.auction_id == auction_id))
            return auction.bid_count, int(rows or 0), auction.current_price
    finally:
        await engine.dispose()


async def run(args: argparse.Namespace) -> int:
    jwt_secret = secrets.token_urlsafe(48)
    env = {
        **os.environ,
        "ADAL_ENV": "test",
        "ADAL_DATABASE_URL": args.database_url,
        "ADAL_JWT_SECRET": jwt_secret,
        "ADAL_MFA_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "ADAL_SCHEDULER_ENABLED": "false",
        "ADAL_MEDIA_DIR": tempfile.mkdtemp(prefix="adal-loadtest-"),
    }
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True, capture_output=True)
    auctions = [await prepare(args.database_url, jwt_secret, args.bidders) for _ in range(args.auctions)]

    def more_files() -> None:  # every watcher is one socket on each side
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        resource.setrlimit(resource.RLIMIT_NOFILE, (min(8192, hard), hard))

    more_files()
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "127.0.0.1", "--port", str(args.port), "--log-level", "warning"],
        cwd=BACKEND, env=env, preexec_fn=more_files,
    )
    base = f"http://127.0.0.1:{args.port}"
    try:
        async with httpx.AsyncClient(base_url=base, timeout=30, limits=httpx.Limits(max_connections=args.bidders * args.auctions + 5)) as http:
            for _ in range(100):
                try:
                    if (await http.get("/api/categories")).status_code == 200:
                        break
                except httpx.TransportError:
                    await asyncio.sleep(0.1)
            else:
                raise SystemExit("the API did not start")

            # per auction, per watcher: bid_count -> delay in seconds
            received: dict[int, list[dict[int, float]]] = {auction_id: [{} for _ in range(args.watchers)] for auction_id, _ in auctions}
            ready = asyncio.Semaphore(0)
            done = asyncio.Event()
            opening = asyncio.Semaphore(200)  # open the sockets in waves, not all in one instant

            async def watch(auction_id: int, index: int) -> None:
                async with opening:
                    socket = await connect(f"ws://127.0.0.1:{args.port}/ws/auctions/{auction_id}", open_timeout=60)
                async with socket:
                    await socket.recv()  # the snapshot
                    ready.release()
                    while not done.is_set():
                        try:
                            event = json.loads(await asyncio.wait_for(socket.recv(), timeout=0.5))
                        except TimeoutError:
                            continue
                        if event["type"] == "bid_placed":
                            placed_at = datetime.fromisoformat(event["bid"]["placed_at"].replace("Z", "+00:00"))
                            received[auction_id][index][event["bid_count"]] = (datetime.now(UTC) - placed_at).total_seconds()

            watchers = [asyncio.create_task(watch(auction_id, i)) for auction_id, _ in auctions for i in range(args.watchers)]
            for _ in watchers:
                await ready.acquire()

            prices = {auction_id: Decimal("99.00") for auction_id, _ in auctions}  # the best price any bidder has seen so far
            accepted = dict.fromkeys(prices, 0)
            bid_seconds: list[float] = []
            outcomes: dict[str, int] = {}

            async def bidder(auction_id: int, token: str, start_after: float) -> None:
                await asyncio.sleep(start_after)  # bidders arrive over a couple of seconds, as people do
                for _ in range(args.bids_each):
                    await asyncio.sleep(args.pause * (0.5 + random.random()))  # think time, spread so bidders do not move in step
                    amount = prices[auction_id] + STEP
                    for attempt in range(5):
                        started = time.perf_counter()
                        try:
                            response = await http.post(f"/api/auctions/{auction_id}/bids", json={"amount": f"{amount:.2f}"}, headers={"Authorization": f"Bearer {token}"})
                            break
                        except httpx.TransportError:  # the operating system refused a new connection in a burst; not the API
                            outcomes["connection_retry"] = outcomes.get("connection_retry", 0) + 1
                            await asyncio.sleep(0.05 * (attempt + 1))
                    else:
                        raise SystemExit("could not reach the API")
                    bid_seconds.append(time.perf_counter() - started)
                    body = response.json()
                    outcome = "accepted" if response.status_code == 201 else body["error"]["code"]
                    outcomes[outcome] = outcomes.get(outcome, 0) + 1
                    if response.status_code == 201:
                        accepted[auction_id] += 1
                        prices[auction_id] = max(prices[auction_id], Decimal(body["bid"]["amount"]))
                    elif outcome == "bid_too_low":
                        prices[auction_id] = max(prices[auction_id], Decimal(body["error"]["details"]["min_next_bid"]) - STEP)

            started = time.perf_counter()
            everyone = [(auction_id, token) for auction_id, tokens in auctions for token in tokens]
            await asyncio.gather(*(bidder(auction_id, token, i * 0.004) for i, (auction_id, token) in enumerate(everyone)))
            elapsed = time.perf_counter() - started
            for _ in range(200):  # let the last events arrive
                if all(len(seen) == accepted[auction_id] for auction_id, per_watcher in received.items() for seen in per_watcher):
                    break
                await asyncio.sleep(0.05)
            done.set()
            await asyncio.gather(*watchers)
    finally:
        server.terminate()
        server.wait(timeout=10)

    consistent = True
    for auction_id, _ in auctions:
        bid_count, stored_bids, stored_price = await stored_result(args.database_url, auction_id)
        consistent = consistent and bid_count == stored_bids == accepted[auction_id] and stored_price == prices[auction_id]
    delays = [delay for per_watcher in received.values() for seen in per_watcher for delay in seen.values()]
    missing = sum(accepted[auction_id] - len(seen) for auction_id, per_watcher in received.items() for seen in per_watcher)
    report = {
        "auctions": args.auctions,
        "watchers_per_auction": args.watchers,
        "bidders_per_auction": args.bidders,
        "open_websockets": len(watchers),
        "pause_seconds": args.pause,
        "requests": len(bid_seconds),
        "outcomes": dict(sorted(outcomes.items())),
        "requests_per_second": round(len(bid_seconds) / elapsed, 1),
        "bid_time": summary("POST /bids, request to response", bid_seconds),
        "delivery_time": summary("bid accepted in the database to watcher", delays),
        "deliveries": len(delays),
        "missing_deliveries": missing,
        "stored_results_match": consistent,
    }
    print(json.dumps(report, indent=2))
    consistent = consistent and missing == 0
    unexpected = set(outcomes) - {"accepted", "bid_too_low", "already_leading", "connection_retry"}
    if not consistent or unexpected:
        print(f"FAILED: inconsistent result or unexpected outcomes {sorted(unexpected)}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.loadtest", description=__doc__.splitlines()[0])
    parser.add_argument("--auctions", type=int, default=1)
    parser.add_argument("--watchers", type=int, default=200, help="per auction")
    parser.add_argument("--bidders", type=int, default=25, help="per auction")
    parser.add_argument("--bids-each", type=int, default=20, help="attempts per bidder (the API allows 30 a minute)")
    parser.add_argument("--pause", type=float, default=0.0, help="average seconds a bidder waits between bids; 0 is a stress test")
    parser.add_argument("--port", type=int, default=8011)
    parser.add_argument("--database-url", default=DEFAULT_DATABASE)
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
