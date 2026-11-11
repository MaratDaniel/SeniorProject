"""English (ascending) auction: FR-21, FR-23, FR-24, DR-3."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from app.engine.base import AuctionState, BidDecision, BidRejected, Outcome, RankedBid, rank_bids


@dataclass(frozen=True)
class EnglishStrategy:
    sniping_window: timedelta = timedelta(minutes=2)
    sniping_extension: timedelta = timedelta(minutes=2)
    name: str = "english"
    bids_visible: bool = True

    def validate_config(self, *, starting_price: Decimal, min_increment: Decimal, starts_at: datetime, ends_at: datetime) -> None:
        if min_increment <= 0:
            raise ValueError("The bid step must be more than zero.")
        if min_increment > starting_price * 10:
            raise ValueError("The bid step is too large for this starting price.")

    def min_next_bid(self, state: AuctionState) -> Decimal:
        if state.current_price is None:
            return state.starting_price  # the first bid only has to meet the starting price
        return state.current_price + state.min_increment

    def accept_bid(self, state: AuctionState, *, bidder_id: int, amount: Decimal, now: datetime) -> BidDecision:
        if state.leader_id == bidder_id:
            raise BidRejected("already_leading", "You already hold the highest bid.")
        minimum = self.min_next_bid(state)
        if amount < minimum:
            raise BidRejected(
                "bid_too_low",
                f"Your bid must be at least {minimum:.2f}.",
                {"min_next_bid": f"{minimum:.2f}"},
            )
        ends_at = state.ends_at
        if ends_at - now <= self.sniping_window:
            ends_at = ends_at + self.sniping_extension  # FR-21: a late bid extends the close
        return BidDecision(price=amount, leader_id=bidder_id, ends_at=ends_at)

    def determine_result(self, state: AuctionState, ranked_bids: Sequence[RankedBid]) -> Outcome:
        ranked = rank_bids(ranked_bids)
        if not ranked:
            return Outcome(winner_id=None, price=None)
        top = ranked[0]
        return Outcome(winner_id=top.bidder_id, price=top.amount)  # the winner pays their own bid

    def report(self, state: AuctionState) -> dict[str, Any]:
        return {"bids_visible": True}
