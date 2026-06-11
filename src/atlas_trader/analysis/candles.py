"""Candlestick analysis helpers."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from statistics import fmean

from atlas_trader.data.models import Candle


class CandleDirection(StrEnum):
    """Basic candle direction."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class CandleStrength(StrEnum):
    """Describes how dominant the candle body is compared to the full range."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    INDECISION = "indecision"


class CandleType(StrEnum):
    """Simple candle classification."""

    STRONG_BULLISH = "strong_bullish"
    STRONG_BEARISH = "strong_bearish"
    INDECISION = "indecision"
    LONG_UPPER_WICK = "long_upper_wick"
    LONG_LOWER_WICK = "long_lower_wick"
    STANDARD = "standard"


class CandleClosePosition(StrEnum):
    """Describes where the candle closed within its high/low range."""

    NEAR_HIGH = "near_high"
    MID_RANGE = "mid_range"
    NEAR_LOW = "near_low"


class CandleRangeContext(StrEnum):
    """Describes current range size compared with recent candle ranges."""

    WIDE = "wide"
    AVERAGE = "average"
    NARROW = "narrow"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CandleAnalysisSettings:
    """Tunable thresholds used by candle analysis."""

    indecision_body_ratio: float = 0.10
    moderate_body_ratio: float = 0.40
    strong_body_ratio: float = 0.70
    long_wick_ratio: float = 0.50
    close_near_low_ratio: float = 0.25
    close_near_high_ratio: float = 0.75
    narrow_range_ratio: float = 0.75
    wide_range_ratio: float = 1.50
    default_range_period: int = 20

    def __post_init__(self) -> None:
        """Validate threshold relationships."""
        if self.default_range_period <= 0:
            raise ValueError("default_range_period must be greater than zero.")
        if (
            not 0
            <= self.indecision_body_ratio
            <= self.moderate_body_ratio
            <= self.strong_body_ratio
            <= 1
        ):
            raise ValueError(
                "body thresholds must satisfy 0 <= indecision <= moderate <= strong <= 1."
            )
        if not 0 <= self.long_wick_ratio <= 1:
            raise ValueError("long_wick_ratio must be between zero and one.")
        if not 0 <= self.close_near_low_ratio <= self.close_near_high_ratio <= 1:
            raise ValueError(
                "close position thresholds must satisfy "
                "0 <= close_near_low <= close_near_high <= 1."
            )
        if not 0 < self.narrow_range_ratio <= self.wide_range_ratio:
            raise ValueError(
                "range thresholds must satisfy 0 < narrow_range_ratio <= wide_range_ratio."
            )


# TODO(v0.7): Move candle-analysis thresholds into a shared analysis config object.
DEFAULT_CANDLE_ANALYSIS_SETTINGS = CandleAnalysisSettings()


@dataclass(frozen=True)
class CandleMetrics:
    """Calculated candle measurements."""

    direction: CandleDirection
    candle_type: CandleType
    strength: CandleStrength
    full_range: float
    body_size: float
    upper_wick_size: float
    lower_wick_size: float
    body_to_range_ratio: float
    upper_wick_to_range_ratio: float
    lower_wick_to_range_ratio: float
    close_position_ratio: float
    close_position: CandleClosePosition


@dataclass(frozen=True)
class CandleContext:
    """One candle's metrics plus its relationship to prior candles."""

    candle: Candle
    metrics: CandleMetrics
    previous_candle: Candle | None
    average_range: float | None
    range_vs_average_ratio: float | None
    range_context: CandleRangeContext
    has_higher_high_than_previous: bool
    has_lower_low_than_previous: bool
    has_higher_low_than_previous: bool
    has_lower_high_than_previous: bool
    closes_above_previous_high: bool
    closes_below_previous_low: bool
    is_inside_bar: bool
    is_outside_bar: bool


def analyze_candle(
    candle: Candle,
    *,
    settings: CandleAnalysisSettings = DEFAULT_CANDLE_ANALYSIS_SETTINGS,
) -> CandleMetrics:
    """Analyze one candle and return its calculated structure."""
    full_range = candle.high - candle.low

    if full_range == 0:
        return CandleMetrics(
            direction=CandleDirection.NEUTRAL,
            candle_type=CandleType.INDECISION,
            strength=CandleStrength.INDECISION,
            full_range=0,
            body_size=0,
            upper_wick_size=0,
            lower_wick_size=0,
            body_to_range_ratio=0,
            upper_wick_to_range_ratio=0,
            lower_wick_to_range_ratio=0,
            close_position_ratio=0,
            close_position=CandleClosePosition.MID_RANGE,
        )

    body_size = abs(candle.close - candle.open)
    candle_body_high = max(candle.open, candle.close)
    candle_body_low = min(candle.open, candle.close)

    upper_wick_size = candle.high - candle_body_high
    lower_wick_size = candle_body_low - candle.low

    body_to_range_ratio = body_size / full_range
    upper_wick_to_range_ratio = upper_wick_size / full_range
    lower_wick_to_range_ratio = lower_wick_size / full_range
    close_position_ratio = (candle.close - candle.low) / full_range

    direction = _classify_direction(candle)
    strength = _classify_strength(body_to_range_ratio, settings)
    candle_type = _classify_type(
        direction=direction,
        strength=strength,
        upper_wick_to_range_ratio=upper_wick_to_range_ratio,
        lower_wick_to_range_ratio=lower_wick_to_range_ratio,
        settings=settings,
    )

    return CandleMetrics(
        direction=direction,
        candle_type=candle_type,
        strength=strength,
        full_range=full_range,
        body_size=body_size,
        upper_wick_size=upper_wick_size,
        lower_wick_size=lower_wick_size,
        body_to_range_ratio=body_to_range_ratio,
        upper_wick_to_range_ratio=upper_wick_to_range_ratio,
        lower_wick_to_range_ratio=lower_wick_to_range_ratio,
        close_position_ratio=close_position_ratio,
        close_position=_classify_close_position(close_position_ratio, settings),
    )


def analyze_candles(
    candles: Sequence[Candle],
    *,
    settings: CandleAnalysisSettings = DEFAULT_CANDLE_ANALYSIS_SETTINGS,
) -> list[CandleMetrics]:
    """Analyze a sequence of candles without adding cross-candle context."""
    return [analyze_candle(candle, settings=settings) for candle in candles]


def analyze_candle_contexts(
    candles: Sequence[Candle],
    average_range_period: int | None = None,
    *,
    settings: CandleAnalysisSettings = DEFAULT_CANDLE_ANALYSIS_SETTINGS,
) -> list[CandleContext]:
    """Analyze candles with previous-candle and rolling range context."""
    average_range_period = (
        settings.default_range_period if average_range_period is None else average_range_period
    )
    if average_range_period <= 0:
        raise ValueError("average_range_period must be greater than zero.")

    contexts: list[CandleContext] = []
    ranges: list[float] = []

    for index, candle in enumerate(candles):
        previous_candle = candles[index - 1] if index > 0 else None
        metrics = analyze_candle(candle, settings=settings)
        average_range = _average_recent_range(ranges, average_range_period)
        range_vs_average_ratio = (
            metrics.full_range / average_range if average_range and average_range > 0 else None
        )

        contexts.append(
            CandleContext(
                candle=candle,
                metrics=metrics,
                previous_candle=previous_candle,
                average_range=average_range,
                range_vs_average_ratio=range_vs_average_ratio,
                range_context=_classify_range_context(range_vs_average_ratio, settings),
                has_higher_high_than_previous=has_higher_high_than_previous(
                    candle,
                    previous_candle,
                ),
                has_lower_low_than_previous=has_lower_low_than_previous(
                    candle,
                    previous_candle,
                ),
                has_higher_low_than_previous=has_higher_low_than_previous(
                    candle,
                    previous_candle,
                ),
                has_lower_high_than_previous=has_lower_high_than_previous(
                    candle,
                    previous_candle,
                ),
                closes_above_previous_high=closes_above_previous_high(candle, previous_candle),
                closes_below_previous_low=closes_below_previous_low(candle, previous_candle),
                is_inside_bar=is_inside_bar(candle, previous_candle),
                is_outside_bar=is_outside_bar(candle, previous_candle),
            )
        )
        ranges.append(metrics.full_range)

    return contexts


def has_higher_high_than_previous(candle: Candle, previous_candle: Candle | None) -> bool:
    """Return whether this candle made a higher high than the previous candle."""
    return previous_candle is not None and candle.high > previous_candle.high


def has_lower_low_than_previous(candle: Candle, previous_candle: Candle | None) -> bool:
    """Return whether this candle made a lower low than the previous candle."""
    return previous_candle is not None and candle.low < previous_candle.low


def has_higher_low_than_previous(candle: Candle, previous_candle: Candle | None) -> bool:
    """Return whether this candle held a higher low than the previous candle."""
    return previous_candle is not None and candle.low > previous_candle.low


def has_lower_high_than_previous(candle: Candle, previous_candle: Candle | None) -> bool:
    """Return whether this candle made a lower high than the previous candle."""
    return previous_candle is not None and candle.high < previous_candle.high


def closes_above_previous_high(candle: Candle, previous_candle: Candle | None) -> bool:
    """Return whether this candle closed above the previous candle's high."""
    return previous_candle is not None and candle.close > previous_candle.high


def closes_below_previous_low(candle: Candle, previous_candle: Candle | None) -> bool:
    """Return whether this candle closed below the previous candle's low."""
    return previous_candle is not None and candle.close < previous_candle.low


def is_inside_bar(candle: Candle, previous_candle: Candle | None) -> bool:
    """Return whether this candle's full range sits inside the previous range."""
    return (
        previous_candle is not None
        and candle.high <= previous_candle.high
        and candle.low >= previous_candle.low
    )


def is_outside_bar(candle: Candle, previous_candle: Candle | None) -> bool:
    """Return whether this candle expands beyond both sides of the previous range."""
    return (
        previous_candle is not None
        and candle.high > previous_candle.high
        and candle.low < previous_candle.low
    )


def _classify_direction(candle: Candle) -> CandleDirection:
    if candle.close > candle.open:
        return CandleDirection.BULLISH

    if candle.close < candle.open:
        return CandleDirection.BEARISH

    return CandleDirection.NEUTRAL


def _classify_strength(
    body_to_range_ratio: float,
    settings: CandleAnalysisSettings,
) -> CandleStrength:
    if body_to_range_ratio <= settings.indecision_body_ratio:
        return CandleStrength.INDECISION

    if body_to_range_ratio >= settings.strong_body_ratio:
        return CandleStrength.STRONG

    if body_to_range_ratio >= settings.moderate_body_ratio:
        return CandleStrength.MODERATE

    return CandleStrength.WEAK


def _classify_close_position(
    close_position_ratio: float,
    settings: CandleAnalysisSettings,
) -> CandleClosePosition:
    if close_position_ratio >= settings.close_near_high_ratio:
        return CandleClosePosition.NEAR_HIGH

    if close_position_ratio <= settings.close_near_low_ratio:
        return CandleClosePosition.NEAR_LOW

    return CandleClosePosition.MID_RANGE


def _classify_range_context(
    range_vs_average_ratio: float | None,
    settings: CandleAnalysisSettings,
) -> CandleRangeContext:
    if range_vs_average_ratio is None:
        return CandleRangeContext.UNKNOWN

    if range_vs_average_ratio >= settings.wide_range_ratio:
        return CandleRangeContext.WIDE

    if range_vs_average_ratio <= settings.narrow_range_ratio:
        return CandleRangeContext.NARROW

    return CandleRangeContext.AVERAGE


def _average_recent_range(ranges: Sequence[float], average_range_period: int) -> float | None:
    if not ranges:
        return None

    return fmean(ranges[-average_range_period:])


def _classify_type(
    direction: CandleDirection,
    strength: CandleStrength,
    upper_wick_to_range_ratio: float,
    lower_wick_to_range_ratio: float,
    settings: CandleAnalysisSettings,
) -> CandleType:
    if strength == CandleStrength.INDECISION:
        return CandleType.INDECISION

    if upper_wick_to_range_ratio >= settings.long_wick_ratio:
        return CandleType.LONG_UPPER_WICK

    if lower_wick_to_range_ratio >= settings.long_wick_ratio:
        return CandleType.LONG_LOWER_WICK

    if direction == CandleDirection.BULLISH and strength == CandleStrength.STRONG:
        return CandleType.STRONG_BULLISH

    if direction == CandleDirection.BEARISH and strength == CandleStrength.STRONG:
        return CandleType.STRONG_BEARISH

    return CandleType.STANDARD
