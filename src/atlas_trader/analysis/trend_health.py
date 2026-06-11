"""Short-term pressure and trend-health helpers for market-reading reports."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from atlas_trader.analysis.moving_averages import (
    MovingAveragePosition,
    MovingAverageReportContext,
)
from atlas_trader.analysis.trends import TrendAnalysis, TrendDirection
from atlas_trader.data.models import Candle


class ShortTermPressure(StrEnum):
    """Recent close pressure."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class TrendCondition(StrEnum):
    """Current trend health against broader structure."""

    STRENGTHENING = "strengthening"
    PULLING_BACK = "pulling_back"
    WEAKENING = "weakening"
    REVERSING_RISK = "reversing_risk"
    SIDEWAYS = "sideways"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TrendHealthSettings:
    """Tunable settings for report-only trend-health context."""

    recent_return_period: int = 5
    recent_extreme_lookback: int = 20
    pressure_return_threshold: float = 0.02
    sharp_pullback_pct: float = 0.05

    def __post_init__(self) -> None:
        """Validate trend-health settings."""
        if self.recent_return_period <= 0:
            raise ValueError("recent_return_period must be greater than zero.")
        if self.recent_extreme_lookback <= 1:
            raise ValueError("recent_extreme_lookback must be greater than one.")
        if self.pressure_return_threshold < 0:
            raise ValueError("pressure_return_threshold cannot be negative.")
        if self.sharp_pullback_pct < 0:
            raise ValueError("sharp_pullback_pct cannot be negative.")


DEFAULT_TREND_HEALTH_SETTINGS = TrendHealthSettings()


@dataclass(frozen=True)
class TrendHealthContext:
    """Short-term condition layered beside broader trend structure."""

    short_term_pressure: ShortTermPressure
    trend_condition: TrendCondition
    recent_return_pct: float | None
    consecutive_down_closes: int
    consecutive_up_closes: int
    pullback_from_recent_high_pct: float | None
    bounce_from_recent_low_pct: float | None
    trend_health_reasons: list[str]


def analyze_trend_health(
    candles: Sequence[Candle],
    *,
    trend: TrendAnalysis,
    moving_average_context: MovingAverageReportContext,
    settings: TrendHealthSettings = DEFAULT_TREND_HEALTH_SETTINGS,
) -> TrendHealthContext:
    """Analyze recent pressure without changing broader trend classification."""
    if len(candles) < 2:
        return TrendHealthContext(
            short_term_pressure=ShortTermPressure.UNKNOWN,
            trend_condition=TrendCondition.UNKNOWN,
            recent_return_pct=None,
            consecutive_down_closes=0,
            consecutive_up_closes=0,
            pullback_from_recent_high_pct=None,
            bounce_from_recent_low_pct=None,
            trend_health_reasons=["insufficient_candles"],
        )

    recent_return_pct = _recent_return_pct(candles, settings.recent_return_period)
    consecutive_down_closes = _consecutive_down_closes(candles)
    consecutive_up_closes = _consecutive_up_closes(candles)
    pullback_from_recent_high_pct = _pullback_from_recent_high_pct(
        candles,
        settings.recent_extreme_lookback,
    )
    bounce_from_recent_low_pct = _bounce_from_recent_low_pct(
        candles,
        settings.recent_extreme_lookback,
    )
    reasons = _trend_health_reasons(
        candles=candles,
        moving_average_context=moving_average_context,
        recent_return_pct=recent_return_pct,
        consecutive_down_closes=consecutive_down_closes,
        consecutive_up_closes=consecutive_up_closes,
        pullback_from_recent_high_pct=pullback_from_recent_high_pct,
        settings=settings,
    )
    pressure = _classify_pressure(
        recent_return_pct=recent_return_pct,
        consecutive_down_closes=consecutive_down_closes,
        consecutive_up_closes=consecutive_up_closes,
        settings=settings,
    )

    return TrendHealthContext(
        short_term_pressure=pressure,
        trend_condition=_classify_condition(
            trend_direction=trend.direction,
            pressure=pressure,
            moving_average_context=moving_average_context,
            reasons=reasons,
        ),
        recent_return_pct=recent_return_pct,
        consecutive_down_closes=consecutive_down_closes,
        consecutive_up_closes=consecutive_up_closes,
        pullback_from_recent_high_pct=pullback_from_recent_high_pct,
        bounce_from_recent_low_pct=bounce_from_recent_low_pct,
        trend_health_reasons=reasons,
    )


def _recent_return_pct(candles: Sequence[Candle], lookback: int) -> float | None:
    if len(candles) <= lookback:
        return None

    start_close = candles[-lookback - 1].close
    if start_close <= 0:
        return None
    return (candles[-1].close - start_close) / start_close


def _consecutive_down_closes(candles: Sequence[Candle]) -> int:
    count = 0
    for previous, current in zip(reversed(candles[:-1]), reversed(candles[1:]), strict=False):
        if current.close < previous.close:
            count += 1
        else:
            break
    return count


def _consecutive_up_closes(candles: Sequence[Candle]) -> int:
    count = 0
    for previous, current in zip(reversed(candles[:-1]), reversed(candles[1:]), strict=False):
        if current.close > previous.close:
            count += 1
        else:
            break
    return count


def _pullback_from_recent_high_pct(
    candles: Sequence[Candle],
    lookback: int,
) -> float | None:
    window = candles[-lookback:]
    recent_high = max(candle.high for candle in window)
    if recent_high <= 0:
        return None
    return (recent_high - candles[-1].close) / recent_high


def _bounce_from_recent_low_pct(
    candles: Sequence[Candle],
    lookback: int,
) -> float | None:
    window = candles[-lookback:]
    recent_low = min(candle.low for candle in window)
    if recent_low <= 0:
        return None
    return (candles[-1].close - recent_low) / recent_low


def _classify_pressure(
    *,
    recent_return_pct: float | None,
    consecutive_down_closes: int,
    consecutive_up_closes: int,
    settings: TrendHealthSettings,
) -> ShortTermPressure:
    if recent_return_pct is None:
        return ShortTermPressure.UNKNOWN
    if recent_return_pct <= -settings.pressure_return_threshold or consecutive_down_closes >= 2:
        return ShortTermPressure.BEARISH
    if recent_return_pct >= settings.pressure_return_threshold or consecutive_up_closes >= 2:
        return ShortTermPressure.BULLISH
    return ShortTermPressure.NEUTRAL


def _classify_condition(
    *,
    trend_direction: TrendDirection,
    pressure: ShortTermPressure,
    moving_average_context: MovingAverageReportContext,
    reasons: Sequence[str],
) -> TrendCondition:
    if trend_direction == TrendDirection.UNKNOWN or pressure == ShortTermPressure.UNKNOWN:
        return TrendCondition.UNKNOWN
    if trend_direction == TrendDirection.SIDEWAYS:
        return TrendCondition.SIDEWAYS

    if trend_direction == TrendDirection.UPTREND:
        if moving_average_context.ema_200.position == MovingAveragePosition.BELOW:
            return TrendCondition.REVERSING_RISK
        if pressure == ShortTermPressure.BEARISH:
            return TrendCondition.PULLING_BACK
        if pressure == ShortTermPressure.BULLISH:
            return TrendCondition.STRENGTHENING
        return (
            TrendCondition.WEAKENING if "price_below_ema20" in reasons else TrendCondition.SIDEWAYS
        )

    if trend_direction == TrendDirection.DOWNTREND:
        if moving_average_context.ema_200.position == MovingAveragePosition.ABOVE:
            return TrendCondition.REVERSING_RISK
        if pressure == ShortTermPressure.BULLISH:
            return TrendCondition.PULLING_BACK
        if pressure == ShortTermPressure.BEARISH:
            return TrendCondition.STRENGTHENING
        return (
            TrendCondition.WEAKENING if "price_above_ema20" in reasons else TrendCondition.SIDEWAYS
        )

    return TrendCondition.UNKNOWN


def _trend_health_reasons(
    *,
    candles: Sequence[Candle],
    moving_average_context: MovingAverageReportContext,
    recent_return_pct: float | None,
    consecutive_down_closes: int,
    consecutive_up_closes: int,
    pullback_from_recent_high_pct: float | None,
    settings: TrendHealthSettings,
) -> list[str]:
    reasons: list[str] = []

    _add_ema_reasons(reasons, moving_average_context)
    if (
        pullback_from_recent_high_pct is not None
        and pullback_from_recent_high_pct >= settings.sharp_pullback_pct
    ):
        reasons.append("sharp_pullback_from_recent_high")
    if recent_return_pct is None:
        reasons.append("recent_return_unknown")
    if consecutive_down_closes >= 2:
        reasons.append("recent_lower_closes")
    if consecutive_up_closes >= 2:
        reasons.append("recent_higher_closes")
    if candles[-1].close > 0 and moving_average_context.ema_200.value is not None:
        if candles[-1].close >= moving_average_context.ema_200.value:
            reasons.append("still_above_ema200")
        else:
            reasons.append("below_ema200")

    return reasons


def _add_ema_reasons(
    reasons: list[str],
    moving_average_context: MovingAverageReportContext,
) -> None:
    ema_levels = (
        moving_average_context.ema_20,
        moving_average_context.ema_50,
        moving_average_context.ema_200,
    )
    for level in ema_levels:
        if level.value is None:
            continue
        if level.position == MovingAveragePosition.NEAR:
            reasons.append(f"testing_ema{level.period}")
        elif level.position == MovingAveragePosition.ABOVE:
            reasons.append(f"price_above_ema{level.period}")
        elif level.position == MovingAveragePosition.BELOW:
            reasons.append(f"price_below_ema{level.period}")
