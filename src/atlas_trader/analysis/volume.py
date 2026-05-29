"""Volume analysis and breakout volume context helpers."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from statistics import fmean

from atlas_trader.analysis.ranges import BreakoutDirection
from atlas_trader.data.models import Candle


class RelativeVolumeLevel(StrEnum):
    """Current volume compared with recent average volume."""

    HIGH = "high"
    AVERAGE = "average"
    LOW = "low"
    UNKNOWN = "unknown"


class VolumeTrend(StrEnum):
    """Short-term direction of recent volume."""

    RISING = "rising"
    FALLING = "falling"
    FLAT = "flat"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class BreakoutVolumeContext(StrEnum):
    """Whether volume confirms a price breakout."""

    CONFIRMED = "confirmed"
    WEAK = "weak"
    ABSENT = "absent"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class VolumeAnalysisSettings:
    """Tunable thresholds used by volume analysis."""

    default_average_period: int = 20
    trend_period: int = 3
    high_relative_volume_ratio: float = 1.50
    low_relative_volume_ratio: float = 0.75
    flat_volume_tolerance_ratio: float = 0.05
    breakout_relative_volume_ratio: float = 1.50

    def __post_init__(self) -> None:
        """Validate volume-analysis settings."""
        if self.default_average_period <= 0:
            raise ValueError("default_average_period must be greater than zero.")
        if self.trend_period <= 1:
            raise ValueError("trend_period must be greater than one.")
        if not 0 < self.low_relative_volume_ratio <= self.high_relative_volume_ratio:
            raise ValueError(
                "relative volume thresholds must satisfy "
                "0 < low_relative_volume_ratio <= high_relative_volume_ratio."
            )
        if self.flat_volume_tolerance_ratio < 0:
            raise ValueError("flat_volume_tolerance_ratio cannot be negative.")
        if self.breakout_relative_volume_ratio <= 0:
            raise ValueError("breakout_relative_volume_ratio must be greater than zero.")


# TODO(v0.7): Move volume-analysis thresholds into a shared analysis config object.
DEFAULT_VOLUME_ANALYSIS_SETTINGS = VolumeAnalysisSettings()


@dataclass(frozen=True)
class VolumeContext:
    """Volume metrics for one candle relative to prior candles."""

    candle: Candle
    average_volume: float | None
    relative_volume: float | None
    relative_volume_level: RelativeVolumeLevel
    volume_trend: VolumeTrend
    breakout_context: BreakoutVolumeContext


def analyze_volume(
    candles: Sequence[Candle],
    *,
    average_period: int | None = None,
    breakout_direction: BreakoutDirection = BreakoutDirection.NONE,
    settings: VolumeAnalysisSettings = DEFAULT_VOLUME_ANALYSIS_SETTINGS,
) -> VolumeContext:
    """Analyze the latest candle's volume against recent volume context."""
    contexts = analyze_volume_contexts(
        candles,
        average_period=average_period,
        breakout_directions=[BreakoutDirection.NONE] * (len(candles) - 1) + [breakout_direction]
        if candles
        else [],
        settings=settings,
    )
    if not contexts:
        raise ValueError("candles must contain at least one candle.")

    return contexts[-1]


def analyze_volume_contexts(
    candles: Sequence[Candle],
    *,
    average_period: int | None = None,
    breakout_directions: Sequence[BreakoutDirection] | None = None,
    settings: VolumeAnalysisSettings = DEFAULT_VOLUME_ANALYSIS_SETTINGS,
) -> list[VolumeContext]:
    """Analyze volume for each candle using prior candles for rolling context."""
    average_period = settings.default_average_period if average_period is None else average_period
    _validate_period(average_period, "average_period")
    _validate_breakout_directions(candles, breakout_directions)

    contexts: list[VolumeContext] = []
    prior_volumes: list[float] = []

    for index, candle in enumerate(candles):
        average = volume_average(prior_volumes, average_period)
        relative = relative_volume(candle.volume, average)
        breakout_direction = (
            BreakoutDirection.NONE if breakout_directions is None else breakout_directions[index]
        )
        contexts.append(
            VolumeContext(
                candle=candle,
                average_volume=average,
                relative_volume=relative,
                relative_volume_level=_classify_relative_volume(relative, settings),
                volume_trend=_classify_volume_trend(
                    [*prior_volumes, candle.volume],
                    settings=settings,
                ),
                breakout_context=_classify_breakout_volume(
                    breakout_direction=breakout_direction,
                    relative_volume_ratio=relative,
                    settings=settings,
                ),
            )
        )
        prior_volumes.append(candle.volume)

    return contexts


def volume_average(volumes: Sequence[float] | Sequence[Candle], period: int) -> float | None:
    """Return the simple moving average of the latest `period` volume values."""
    _validate_period(period, "period")
    volume_values = _as_volumes(volumes)
    if len(volume_values) < period:
        return None

    return fmean(volume_values[-period:])


def relative_volume(current_volume: float, average_volume: float | None) -> float | None:
    """Return current volume divided by average volume."""
    if average_volume is None or average_volume <= 0:
        return None

    return current_volume / average_volume


def volume_trend(
    volumes: Sequence[float] | Sequence[Candle],
    *,
    settings: VolumeAnalysisSettings = DEFAULT_VOLUME_ANALYSIS_SETTINGS,
) -> VolumeTrend:
    """Classify recent volume as rising, falling, flat, mixed, or unknown."""
    return _classify_volume_trend(_as_volumes(volumes), settings=settings)


def _validate_period(period: int, name: str) -> None:
    if period <= 0:
        raise ValueError(f"{name} must be greater than zero.")


def _validate_breakout_directions(
    candles: Sequence[Candle],
    breakout_directions: Sequence[BreakoutDirection] | None,
) -> None:
    if breakout_directions is not None and len(breakout_directions) != len(candles):
        raise ValueError("breakout_directions must match candles length.")


def _as_volumes(values: Sequence[float] | Sequence[Candle]) -> list[float]:
    return [value.volume if isinstance(value, Candle) else value for value in values]


def _classify_relative_volume(
    relative_volume_ratio: float | None,
    settings: VolumeAnalysisSettings,
) -> RelativeVolumeLevel:
    if relative_volume_ratio is None:
        return RelativeVolumeLevel.UNKNOWN

    if relative_volume_ratio >= settings.high_relative_volume_ratio:
        return RelativeVolumeLevel.HIGH

    if relative_volume_ratio <= settings.low_relative_volume_ratio:
        return RelativeVolumeLevel.LOW

    return RelativeVolumeLevel.AVERAGE


def _classify_volume_trend(
    volumes: Sequence[float],
    *,
    settings: VolumeAnalysisSettings,
) -> VolumeTrend:
    if len(volumes) < settings.trend_period:
        return VolumeTrend.UNKNOWN

    recent_volumes = volumes[-settings.trend_period :]
    changes = [
        _classify_volume_change(previous, current, settings.flat_volume_tolerance_ratio)
        for previous, current in zip(recent_volumes, recent_volumes[1:], strict=False)
    ]

    if all(change == VolumeTrend.RISING for change in changes):
        return VolumeTrend.RISING

    if all(change == VolumeTrend.FALLING for change in changes):
        return VolumeTrend.FALLING

    if all(change == VolumeTrend.FLAT for change in changes):
        return VolumeTrend.FLAT

    return VolumeTrend.MIXED


def _classify_volume_change(
    previous_volume: float,
    current_volume: float,
    flat_tolerance_ratio: float,
) -> VolumeTrend:
    if previous_volume <= 0:
        if current_volume <= 0:
            return VolumeTrend.FLAT
        return VolumeTrend.RISING

    change_ratio = (current_volume - previous_volume) / previous_volume
    if abs(change_ratio) <= flat_tolerance_ratio:
        return VolumeTrend.FLAT
    if change_ratio > 0:
        return VolumeTrend.RISING
    return VolumeTrend.FALLING


def _classify_breakout_volume(
    *,
    breakout_direction: BreakoutDirection,
    relative_volume_ratio: float | None,
    settings: VolumeAnalysisSettings,
) -> BreakoutVolumeContext:
    if breakout_direction == BreakoutDirection.NONE:
        return BreakoutVolumeContext.ABSENT

    if relative_volume_ratio is None:
        return BreakoutVolumeContext.UNKNOWN

    if relative_volume_ratio >= settings.breakout_relative_volume_ratio:
        return BreakoutVolumeContext.CONFIRMED

    return BreakoutVolumeContext.WEAK
