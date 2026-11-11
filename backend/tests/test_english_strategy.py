"""The English strategy on its own: no database, no clock, just the rules (FR-19, FR-21, FR-23, FR-24)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.engine.base import AuctionState, BidDecision, BidRejected, Outcome, RankedBid, StrategyRegistry
from app.engine.english import EnglishStrategy

NOW = datetime(2026, 11, 12, 18, 0, tzinfo=UTC)
english = EnglishStrategy()


def state(current: str | None = None, leader: int | None = None, ends_in: timedelta = timedelta(hours=1)) -> AuctionState:
    return AuctionState(
        starts_at=NOW - timedelta(hours=1),
        ends_at=NOW + ends_in,
        starting_price=Decimal("100.00"),
        min_increment=Decimal("5.00"),
        current_price=Decimal(current) if current else None,
        leader_id=leader,
        bid_count=0 if current is None else 1,
    )


def test_first_bid_only_needs_the_starting_price() -> None:
    decision = english.accept_bid(state(), bidder_id=1, amount=Decimal("100.00"), now=NOW)
    assert decision.price == Decimal("100.00") and decision.leader_id == 1
    with pytest.raises(BidRejected) as low:
        english.accept_bid(state(), bidder_id=1, amount=Decimal("99.99"), now=NOW)
    assert low.value.code == "bid_too_low" and low.value.details == {"min_next_bid": "100.00"}


def test_later_bids_need_the_increment() -> None:
    assert english.min_next_bid(state("120.00", leader=1)) == Decimal("125.00")
    english.accept_bid(state("120.00", leader=1), bidder_id=2, amount=Decimal("125.00"), now=NOW)
    with pytest.raises(BidRejected) as low:
        english.accept_bid(state("120.00", leader=1), bidder_id=2, amount=Decimal("124.99"), now=NOW)
    assert low.value.code == "bid_too_low"


def test_the_leader_cannot_raise_against_themselves() -> None:
    with pytest.raises(BidRejected) as again:
        english.accept_bid(state("120.00", leader=7), bidder_id=7, amount=Decimal("200.00"), now=NOW)
    assert again.value.code == "already_leading"


def test_a_late_bid_extends_the_close_by_the_extension() -> None:
    late = state("120.00", leader=1, ends_in=timedelta(seconds=90))
    decision = english.accept_bid(late, bidder_id=2, amount=Decimal("125.00"), now=NOW)
    assert decision.ends_at == late.ends_at + timedelta(minutes=2)
    early = state("120.00", leader=1, ends_in=timedelta(minutes=10))
    assert english.accept_bid(early, bidder_id=2, amount=Decimal("125.00"), now=NOW).ends_at == early.ends_at


def test_winner_is_highest_then_earliest_then_lowest_id() -> None:
    bids = [
        RankedBid(id=3, bidder_id=30, amount=Decimal("150.00"), placed_at=NOW),
        RankedBid(id=2, bidder_id=20, amount=Decimal("150.00"), placed_at=NOW),
        RankedBid(id=1, bidder_id=10, amount=Decimal("150.00"), placed_at=NOW + timedelta(seconds=1)),
        RankedBid(id=4, bidder_id=40, amount=Decimal("140.00"), placed_at=NOW - timedelta(minutes=1)),
    ]
    assert english.determine_result(state(), bids) == Outcome(winner_id=20, price=Decimal("150.00"))
    assert english.determine_result(state(), []) == Outcome(winner_id=None, price=None)


def test_a_new_format_is_one_registered_strategy() -> None:
    """FR-15 / NFR-7: adding a format does not touch the engine."""

    class FixedPrice:
        name = "fixed_price"
        bids_visible = True

        def validate_config(self, **_: object) -> None:
            return None

        def min_next_bid(self, s: AuctionState) -> Decimal:
            return s.starting_price

        def accept_bid(self, s: AuctionState, *, bidder_id: int, amount: Decimal, now: datetime) -> BidDecision:
            return BidDecision(price=s.starting_price, leader_id=bidder_id, ends_at=now)

        def determine_result(self, s: AuctionState, ranked_bids: list[RankedBid]) -> Outcome:
            return Outcome(winner_id=ranked_bids[0].bidder_id, price=s.starting_price) if ranked_bids else Outcome(None, None)

        def report(self, s: AuctionState) -> dict:
            return {}

    registry = StrategyRegistry()
    registry.register(english)
    registry.register(FixedPrice())
    assert registry.names() == ["english", "fixed_price"]
    assert registry.get("fixed_price").accept_bid(state(), bidder_id=5, amount=Decimal("1"), now=NOW).price == Decimal("100.00")
    with pytest.raises(ValueError):
        registry.register(EnglishStrategy())
