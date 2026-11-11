"""Which formats are switched on. Spring 2027 adds Dutch, sealed first-price and Vickrey here."""

from datetime import timedelta

from app.config import Settings
from app.engine.base import StrategyRegistry
from app.engine.english import EnglishStrategy


def default_registry(settings: Settings) -> StrategyRegistry:
    registry = StrategyRegistry()
    registry.register(
        EnglishStrategy(
            sniping_window=timedelta(seconds=settings.sniping_window_seconds),
            sniping_extension=timedelta(seconds=settings.sniping_extension_seconds),
        )
    )
    return registry
