"""Moving-average context helpers for market-reading reports."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from atlas_trader.data.models import Candle


class MovingAveragePosition(StrEnum):
    """Latest close position relative to a moving average."""

    ABOVE = "above"
    BELOW = "below"
    NEAR = "near"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MovingAverageContextSettings:
    """Tunable settings for report-only moving-average context."""

    ema_periods: tuple[int, int, int] = (20, 50, 200)
    proximity_ratio: float = 0.02

    def __post_init__(self) -> None:
        """Validate moving-average context settings."""
        if not self.ema_periods:
            raise ValueError("ema_periods must not be empty.")
        if any(period <= 0 for period in self.ema_periods):
            raise ValueError("ema_periods must be greater than zero.")
        if self.proximity_ratio < 0:
            raise ValueError("proximity_ratio cannot be negative.")


DEFAULT_MOVING_AVERAGE_CONTEXT_SETTINGS = MovingAverageContextSettings()


@dataclass(frozen=True)
class MovingAverageLevel:
    """One moving average level around the latest close."""

    name: str
    period: int
    value: float | None
    position: MovingAveragePosition
    distance_from_close: float | None
    distance_from_close_pct: float | None


@dataclass(frozen=True)
class MovingAverageReportContext:
    """EMA context for a candle window."""

    ema_20: MovingAverageLevel
    ema_50: MovingAverageLevel
    ema_200: MovingAverageLevel
    nearest_ma_support: MovingAverageLevel | None
    nearest_ma_resistance: MovingAverageLevel | None


def exponential_moving_average(values: Sequence[float], period: int) -> float | None:
    """Return the latest exponential moving average value."""
    _validate_period(period)
    if len(values) < period:
        return None

    alpha = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for value in values[period:]:
        ema = value * alpha + ema * (1 - alpha)
    return ema


def candle_close_exponential_moving_average(
    candles: Sequence[Candle],
    period: int,
) -> float | None:
    """Return the latest close-price EMA value."""
    return exponential_moving_average([candle.close for candle in candles], period)


def analyze_moving_average_context(
    candles: Sequence[Candle],
    *,
    settings: MovingAverageContextSettings = DEFAULT_MOVING_AVERAGE_CONTEXT_SETTINGS,
) -> MovingAverageReportContext:
    """Analyze latest close against EMA 20, EMA 50, and EMA 200."""
    level_by_period = {
        period: _ema_level(candles, period, settings.proximity_ratio)
        for period in settings.ema_periods
    }
    ema_20 = level_by_period.get(20, _unknown_level(20))
    ema_50 = level_by_period.get(50, _unknown_level(50))
    ema_200 = level_by_period.get(200, _unknown_level(200))

    levels = list(level_by_period.values())
    return MovingAverageReportContext(
        ema_20=ema_20,
        ema_50=ema_50,
        ema_200=ema_200,
        nearest_ma_support=_nearest_ma_support(levels),
        nearest_ma_resistance=_nearest_ma_resistance(levels),
    )


def _validate_period(period: int) -> None:
    if period <= 0:
        raise ValueError("period must be greater than zero.")


def _ema_level(
    candles: Sequence[Candle],
    period: int,
    proximity_ratio: float,
) -> MovingAverageLevel:
    value = candle_close_exponential_moving_average(candles, period)
    if not candles or value is None:
        return _unknown_level(period)

    latest_close = candles[-1].close
    distance = latest_close - value
    distance_pct = distance / latest_close
    return MovingAverageLevel(
        name=f"EMA{period}",
        period=period,
        value=value,
        position=_position_for(latest_close, value, proximity_ratio),
        distance_from_close=distance,
        distance_from_close_pct=distance_pct,
    )


def _unknown_level(period: int) -> MovingAverageLevel:
    return MovingAverageLevel(
        name=f"EMA{period}",
        period=period,
        value=None,
        position=MovingAveragePosition.UNKNOWN,
        distance_from_close=None,
        distance_from_close_pct=None,
    )


def _position_for(
    latest_close: float,
    moving_average: float,
    proximity_ratio: float,
) -> MovingAveragePosition:
    if latest_close <= 0 or moving_average <= 0:
        return MovingAveragePosition.UNKNOWN

    if abs(latest_close - moving_average) / latest_close <= proximity_ratio:
        return MovingAveragePosition.NEAR
    if latest_close > moving_average:
        return MovingAveragePosition.ABOVE
    return MovingAveragePosition.BELOW


def _nearest_ma_support(
    levels: Sequence[MovingAverageLevel],
) -> MovingAverageLevel | None:
    candidates = [
        level
        for level in levels
        if level.value is not None
        and level.distance_from_close is not None
        and level.distance_from_close >= 0
        and level.position in {MovingAveragePosition.ABOVE, MovingAveragePosition.NEAR}
    ]
    if not candidates:
        return None

    return min(candidates, key=lambda level: abs(level.distance_from_close or 0))


def _nearest_ma_resistance(
    levels: Sequence[MovingAverageLevel],
) -> MovingAverageLevel | None:
    candidates = [
        level
        for level in levels
        if level.value is not None
        and level.distance_from_close is not None
        and level.distance_from_close <= 0
        and level.position in {MovingAveragePosition.BELOW, MovingAveragePosition.NEAR}
    ]
    if not candidates:
        return None

    return min(candidates, key=lambda level: abs(level.distance_from_close or 0))
