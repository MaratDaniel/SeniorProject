"""The strategy interface every auction format implements (FR-14, FR-15, NFR-7).

A strategy only decides what a valid bid is and who wins. It never touches the
database, the clock or the lock: the engine (service.py) owns those, so adding a
format cannot weaken the concurrency guarantees.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol


class BidRejected(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class AuctionState:
    """What a strategy may read: the auction as of the locked row."""

    starts_at: datetime
    ends_at: datetime
    starting_price: Decimal
    min_increment: Decimal
    current_price: Decimal | None
    leader_id: int | None
    bid_count: int


@dataclass(frozen=True)
class BidDecision:
    price: Decimal  # the new current price
    leader_id: int
    ends_at: datetime  # unchanged, or later if the format extends the close


@dataclass(frozen=True)
class RankedBid:
    id: int
    bidder_id: int
    amount: Decimal
    placed_at: datetime


@dataclass(frozen=True)
class Outcome:
    winner_id: int | None
    price: Decimal | None


class AuctionStrategy(Protocol):
    name: str
    bids_visible: bool  # False for sealed formats: watchers see only a count

    def validate_config(self, *, starting_price: Decimal, min_increment: Decimal, starts_at: datetime, ends_at: datetime) -> None:
        """'create': reject a configuration this format cannot run. Raise ValueError with a user-facing message."""

    def min_next_bid(self, state: AuctionState) -> Decimal:
        """The smallest amount the next bid may have."""

    def accept_bid(self, state: AuctionState, *, bidder_id: int, amount: Decimal, now: datetime) -> BidDecision:
        """'collect bids': validate one bid against the current state, or raise BidRejected."""

    def determine_result(self, state: AuctionState, ranked_bids: Sequence[RankedBid]) -> Outcome:
        """'determine winner and price' from bids ranked by the shared tie-break (FR-19)."""

    def report(self, state: AuctionState) -> dict[str, Any]:
        """'report result': format-specific facts shown to watchers."""


def rank_bids(bids: Iterable[RankedBid]) -> list[RankedBid]:
    """Shared tie-break (FR-19): highest amount, then earliest server time, then lowest id."""
    return sorted(bids, key=lambda b: (-b.amount, b.placed_at, b.id))


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, AuctionStrategy] = {}

    def register(self, strategy: AuctionStrategy) -> AuctionStrategy:
        if strategy.name in self._strategies:
            raise ValueError(f"format already registered: {strategy.name}")
        self._strategies[strategy.name] = strategy
        return strategy

    def get(self, name: str) -> AuctionStrategy:
        try:
            return self._strategies[name]
        except KeyError:
            raise LookupError(f"no strategy for format {name!r}") from None

    def names(self) -> list[str]:
        return sorted(self._strategies)

    def __contains__(self, name: object) -> bool:
        return name in self._strategies
