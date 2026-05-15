"""Core market data models for AtlasTrader."""

from dataclasses import dataclass
from datetime import datetime
from math import isfinite


@dataclass(frozen=True)
class Candle:
    """Represents one OHLCV market candle."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        """Validate candle price and volume data."""
        if not all(isfinite(value) for value in (self.open, self.high, self.low, self.close)):
            raise ValueError("Candle prices must be finite numbers.")

        if not isfinite(self.volume):
            raise ValueError("Candle volume must be a finite number.")

        if self.high < self.low:
            raise ValueError("Candle high cannot be lower than candle low.")

        if self.open <= 0 or self.high <= 0 or self.low <= 0 or self.close <= 0:
            raise ValueError("Candle prices must be greater than zero.")

        if self.volume < 0:
            raise ValueError("Candle volume cannot be negative.")

        if self.open > self.high or self.open < self.low:
            raise ValueError("Candle open must be within the high/low range.")

        if self.close > self.high or self.close < self.low:
            raise ValueError("Candle close must be within the high/low range.")
