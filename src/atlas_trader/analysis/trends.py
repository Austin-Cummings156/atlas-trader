"""Trend and swing-structure analysis helpers."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from atlas_trader.data.models import Candle


class SwingPointType(StrEnum):
    """Type of local price extreme."""

    HIGH = "high"
    LOW = "low"


class TrendDirection(StrEnum):
    """Broad market direction inferred from swing structure."""

    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    SIDEWAYS = "sideways"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TrendAnalysisSettings:
    """Tunable thresholds used by trend analysis."""

    default_swing_strength: int = 2
    min_swing_pairs: int = 2
    min_trend_confidence: float = 0.75

    def __post_init__(self) -> None:
        """Validate trend-analysis settings."""
        if self.default_swing_strength <= 0:
            raise ValueError("default_swing_strength must be greater than zero.")
        if self.min_swing_pairs <= 0:
            raise ValueError("min_swing_pairs must be greater than zero.")
        if not 0 <= self.min_trend_confidence <= 1:
            raise ValueError("min_trend_confidence must be between zero and one.")


# TODO(v0.7): Move trend-analysis thresholds into a shared analysis config object.
DEFAULT_TREND_ANALYSIS_SETTINGS = TrendAnalysisSettings()


@dataclass(frozen=True)
class SwingPoint:
    """A confirmed local high or low."""

    index: int
    candle: Candle
    point_type: SwingPointType
    price: float


@dataclass(frozen=True)
class TrendAnalysis:
    """Summary of trend structure based on confirmed swing highs and lows."""

    direction: TrendDirection
    confidence: float
    swing_highs: list[SwingPoint]
    swing_lows: list[SwingPoint]
    higher_high_count: int
    higher_low_count: int
    lower_high_count: int
    lower_low_count: int
    equal_high_count: int
    equal_low_count: int

    @property
    def latest_swing_high(self) -> SwingPoint | None:
        """Return the latest confirmed swing high."""
        return self.swing_highs[-1] if self.swing_highs else None

    @property
    def latest_swing_low(self) -> SwingPoint | None:
        """Return the latest confirmed swing low."""
        return self.swing_lows[-1] if self.swing_lows else None


def find_swing_points(
    candles: Sequence[Candle],
    strength: int | None = None,
    *,
    settings: TrendAnalysisSettings = DEFAULT_TREND_ANALYSIS_SETTINGS,
) -> list[SwingPoint]:
    """Find confirmed swing highs and lows.

    A swing point must be strictly higher or lower than `strength` candles on both sides.
    Equal highs/lows are intentionally ignored because they describe range boundaries better
    than clean trend structure.
    """
    strength = _resolve_strength(strength, settings)

    swing_points: list[SwingPoint] = []
    if len(candles) < strength * 2 + 1:
        return swing_points

    for index in range(strength, len(candles) - strength):
        candle = candles[index]
        neighbors = [*candles[index - strength : index], *candles[index + 1 : index + strength + 1]]

        if all(candle.high > neighbor.high for neighbor in neighbors):
            swing_points.append(
                SwingPoint(
                    index=index,
                    candle=candle,
                    point_type=SwingPointType.HIGH,
                    price=candle.high,
                )
            )

        if all(candle.low < neighbor.low for neighbor in neighbors):
            swing_points.append(
                SwingPoint(
                    index=index,
                    candle=candle,
                    point_type=SwingPointType.LOW,
                    price=candle.low,
                )
            )

    return sorted(swing_points, key=lambda point: (point.index, point.point_type))


def find_swing_highs(
    candles: Sequence[Candle],
    strength: int | None = None,
    *,
    settings: TrendAnalysisSettings = DEFAULT_TREND_ANALYSIS_SETTINGS,
) -> list[SwingPoint]:
    """Find confirmed swing highs."""
    return [
        point
        for point in find_swing_points(candles, strength, settings=settings)
        if point.point_type == SwingPointType.HIGH
    ]


def find_swing_lows(
    candles: Sequence[Candle],
    strength: int | None = None,
    *,
    settings: TrendAnalysisSettings = DEFAULT_TREND_ANALYSIS_SETTINGS,
) -> list[SwingPoint]:
    """Find confirmed swing lows."""
    return [
        point
        for point in find_swing_points(candles, strength, settings=settings)
        if point.point_type == SwingPointType.LOW
    ]


def analyze_trend(
    candles: Sequence[Candle],
    strength: int | None = None,
    min_swing_pairs: int | None = None,
    min_trend_confidence: float | None = None,
    *,
    settings: TrendAnalysisSettings = DEFAULT_TREND_ANALYSIS_SETTINGS,
) -> TrendAnalysis:
    """Analyze trend direction from higher-high/higher-low or lower-high/lower-low structure."""
    strength = _resolve_strength(strength, settings)
    min_swing_pairs = settings.min_swing_pairs if min_swing_pairs is None else min_swing_pairs
    min_trend_confidence = (
        settings.min_trend_confidence if min_trend_confidence is None else min_trend_confidence
    )
    _validate_min_swing_pairs(min_swing_pairs)
    _validate_min_trend_confidence(min_trend_confidence)

    swing_points = find_swing_points(candles, strength, settings=settings)
    swing_highs = [point for point in swing_points if point.point_type == SwingPointType.HIGH]
    swing_lows = [point for point in swing_points if point.point_type == SwingPointType.LOW]

    high_counts = _count_swing_progression(swing_highs)
    low_counts = _count_swing_progression(swing_lows)

    direction, confidence = _classify_trend(
        high_counts=high_counts,
        low_counts=low_counts,
        swing_high_count=len(swing_highs),
        swing_low_count=len(swing_lows),
        min_swing_pairs=min_swing_pairs,
        min_trend_confidence=min_trend_confidence,
    )

    return TrendAnalysis(
        direction=direction,
        confidence=confidence,
        swing_highs=swing_highs,
        swing_lows=swing_lows,
        higher_high_count=high_counts[0],
        higher_low_count=low_counts[0],
        lower_high_count=high_counts[1],
        lower_low_count=low_counts[1],
        equal_high_count=high_counts[2],
        equal_low_count=low_counts[2],
    )


def _validate_strength(strength: int) -> None:
    if strength <= 0:
        raise ValueError("strength must be greater than zero.")


def _resolve_strength(strength: int | None, settings: TrendAnalysisSettings) -> int:
    resolved_strength = settings.default_swing_strength if strength is None else strength
    _validate_strength(resolved_strength)
    return resolved_strength


def _validate_min_swing_pairs(min_swing_pairs: int) -> None:
    if min_swing_pairs <= 0:
        raise ValueError("min_swing_pairs must be greater than zero.")


def _validate_min_trend_confidence(min_trend_confidence: float) -> None:
    if not 0 <= min_trend_confidence <= 1:
        raise ValueError("min_trend_confidence must be between zero and one.")


def _count_swing_progression(points: Sequence[SwingPoint]) -> tuple[int, int, int]:
    rising = 0
    falling = 0
    equal = 0

    for previous, current in zip(points, points[1:], strict=False):
        if current.price > previous.price:
            rising += 1
        elif current.price < previous.price:
            falling += 1
        else:
            equal += 1

    return rising, falling, equal


def _classify_trend(
    *,
    high_counts: tuple[int, int, int],
    low_counts: tuple[int, int, int],
    swing_high_count: int,
    swing_low_count: int,
    min_swing_pairs: int,
    min_trend_confidence: float,
) -> tuple[TrendDirection, float]:
    if swing_high_count < min_swing_pairs or swing_low_count < min_swing_pairs:
        return TrendDirection.UNKNOWN, 0

    higher_highs, lower_highs, equal_highs = high_counts
    higher_lows, lower_lows, equal_lows = low_counts

    up_score = higher_highs + higher_lows
    down_score = lower_highs + lower_lows
    sideways_score = equal_highs + equal_lows
    comparisons = up_score + down_score + sideways_score

    if comparisons == 0:
        return TrendDirection.UNKNOWN, 0

    confidence = max(up_score, down_score, sideways_score) / comparisons

    if (
        up_score > down_score
        and confidence >= min_trend_confidence
        and higher_highs > 0
        and higher_lows > 0
    ):
        return TrendDirection.UPTREND, confidence

    if (
        down_score > up_score
        and confidence >= min_trend_confidence
        and lower_highs > 0
        and lower_lows > 0
    ):
        return TrendDirection.DOWNTREND, confidence

    return TrendDirection.SIDEWAYS, confidence
