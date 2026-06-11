"""Volatility context helpers for market-reading reports."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from statistics import fmean

from atlas_trader.data.models import Candle


class VolatilityLevel(StrEnum):
    """Simple volatility regime classification."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class VolatilityAnalysisSettings:
    """Tunable thresholds used by volatility context analysis."""

    recent_period: int = 14
    baseline_period: int = 60
    min_baseline_period: int = 20
    low_relative_volatility_ratio: float = 0.75
    high_relative_volatility_ratio: float = 1.50
    extreme_relative_volatility_ratio: float = 2.25
    low_atr_pct: float = 0.01
    high_atr_pct: float = 0.04
    extreme_atr_pct: float = 0.08

    def __post_init__(self) -> None:
        """Validate volatility-analysis settings."""
        if self.recent_period <= 0:
            raise ValueError("recent_period must be greater than zero.")
        if self.baseline_period <= 0:
            raise ValueError("baseline_period must be greater than zero.")
        if self.min_baseline_period <= 0:
            raise ValueError("min_baseline_period must be greater than zero.")
        if self.min_baseline_period > self.baseline_period:
            raise ValueError("min_baseline_period cannot be greater than baseline_period.")
        if not (
            0
            < self.low_relative_volatility_ratio
            <= self.high_relative_volatility_ratio
            <= self.extreme_relative_volatility_ratio
        ):
            raise ValueError(
                "relative volatility thresholds must satisfy 0 < low <= high <= extreme."
            )
        if not 0 < self.low_atr_pct <= self.high_atr_pct <= self.extreme_atr_pct:
            raise ValueError("ATR percent thresholds must satisfy 0 < low <= high <= extreme.")


DEFAULT_VOLATILITY_ANALYSIS_SETTINGS = VolatilityAnalysisSettings()


@dataclass(frozen=True)
class VolatilityContext:
    """Volatility metrics for a candle window."""

    level: VolatilityLevel
    average_true_range: float | None
    average_true_range_pct: float | None
    average_high_low_range_pct: float | None
    baseline_average_true_range_pct: float | None
    recent_vs_baseline_atr_ratio: float | None
    recent_period: int
    baseline_period: int
    insufficient_data_reason: str | None


def analyze_volatility(
    candles: Sequence[Candle],
    *,
    settings: VolatilityAnalysisSettings = DEFAULT_VOLATILITY_ANALYSIS_SETTINGS,
) -> VolatilityContext:
    """Analyze recent volatility relative to the symbol's own recent baseline."""
    if len(candles) < settings.recent_period:
        return _unknown_context(
            settings,
            f"requires at least {settings.recent_period} candles for recent volatility",
        )
    if len(candles) < settings.min_baseline_period:
        return _unknown_context(
            settings,
            f"requires at least {settings.min_baseline_period} candles for baseline volatility",
        )

    true_ranges = true_range_values(candles)
    true_range_pcts = true_range_percent_values(candles)
    recent_true_ranges = true_ranges[-settings.recent_period :]
    recent_true_range_pcts = true_range_pcts[-settings.recent_period :]
    baseline_true_range_pcts = true_range_pcts[-settings.baseline_period :]
    recent_candles = candles[-settings.recent_period :]

    average_true_range = fmean(recent_true_ranges)
    average_true_range_pct = fmean(recent_true_range_pcts)
    baseline_average_true_range_pct = fmean(baseline_true_range_pcts)
    recent_vs_baseline_ratio = (
        average_true_range_pct / baseline_average_true_range_pct
        if baseline_average_true_range_pct > 0
        else None
    )
    average_high_low_range_pct = fmean(high_low_range_pct(candle) for candle in recent_candles)

    return VolatilityContext(
        level=_classify_volatility(
            average_true_range_pct=average_true_range_pct,
            recent_vs_baseline_ratio=recent_vs_baseline_ratio,
            settings=settings,
        ),
        average_true_range=average_true_range,
        average_true_range_pct=average_true_range_pct,
        average_high_low_range_pct=average_high_low_range_pct,
        baseline_average_true_range_pct=baseline_average_true_range_pct,
        recent_vs_baseline_atr_ratio=recent_vs_baseline_ratio,
        recent_period=settings.recent_period,
        baseline_period=min(len(baseline_true_range_pcts), settings.baseline_period),
        insufficient_data_reason=None,
    )


def true_range_values(candles: Sequence[Candle]) -> list[float]:
    """Return true range values for a candle sequence."""
    true_ranges: list[float] = []
    previous_close: float | None = None

    for candle in candles:
        high_low_range = candle.high - candle.low
        if previous_close is None:
            true_range = high_low_range
        else:
            true_range = max(
                high_low_range,
                abs(candle.high - previous_close),
                abs(candle.low - previous_close),
            )
        true_ranges.append(true_range)
        previous_close = candle.close

    return true_ranges


def true_range_percent_values(candles: Sequence[Candle]) -> list[float]:
    """Return true range as a percentage of each candle close."""
    return [
        true_range / candle.close
        for true_range, candle in zip(true_range_values(candles), candles, strict=False)
    ]


def high_low_range_pct(candle: Candle) -> float:
    """Return high-low range as a percentage of candle midpoint."""
    midpoint = (candle.high + candle.low) / 2
    return (candle.high - candle.low) / midpoint


def _classify_volatility(
    *,
    average_true_range_pct: float,
    recent_vs_baseline_ratio: float | None,
    settings: VolatilityAnalysisSettings,
) -> VolatilityLevel:
    if (
        average_true_range_pct >= settings.extreme_atr_pct
        or recent_vs_baseline_ratio is not None
        and recent_vs_baseline_ratio >= settings.extreme_relative_volatility_ratio
    ):
        return VolatilityLevel.EXTREME

    if (
        average_true_range_pct >= settings.high_atr_pct
        or recent_vs_baseline_ratio is not None
        and recent_vs_baseline_ratio >= settings.high_relative_volatility_ratio
    ):
        return VolatilityLevel.HIGH

    if (
        average_true_range_pct <= settings.low_atr_pct
        or recent_vs_baseline_ratio is not None
        and recent_vs_baseline_ratio <= settings.low_relative_volatility_ratio
    ):
        return VolatilityLevel.LOW

    return VolatilityLevel.NORMAL


def _unknown_context(
    settings: VolatilityAnalysisSettings,
    insufficient_data_reason: str,
) -> VolatilityContext:
    return VolatilityContext(
        level=VolatilityLevel.UNKNOWN,
        average_true_range=None,
        average_true_range_pct=None,
        average_high_low_range_pct=None,
        baseline_average_true_range_pct=None,
        recent_vs_baseline_atr_ratio=None,
        recent_period=settings.recent_period,
        baseline_period=settings.baseline_period,
        insufficient_data_reason=insufficient_data_reason,
    )
