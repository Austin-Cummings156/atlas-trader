"""Multi-timeframe market context helpers."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from atlas_trader.analysis.ranges import (
    BreakoutDirection,
    SidewaysMarketAnalysis,
    analyze_sideways_market,
)
from atlas_trader.analysis.support_resistance import (
    SupportResistanceAnalysis,
    analyze_support_resistance,
)
from atlas_trader.analysis.trends import TrendAnalysis, TrendDirection, analyze_trend
from atlas_trader.analysis.volume import (
    BreakoutVolumeContext,
    VolumeContext,
    analyze_volume,
)
from atlas_trader.data.models import Candle


class TimeframeRole(StrEnum):
    """How a timeframe is used in swing/position market reading."""

    RECENT = "recent"
    PRIMARY = "primary"
    LONG_TERM = "long_term"
    SUPPORTING = "supporting"


class TimeframeBias(StrEnum):
    """Directional read for one timeframe."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"
    UNKNOWN = "unknown"


class MultiTimeframeAlignment(StrEnum):
    """Agreement state across analyzed timeframes."""

    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    STRONG_BEARISH = "strong_bearish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"
    CONFLICTED = "conflicted"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MultiTimeframeSettings:
    """Tunable settings for combining multiple timeframe reads."""

    recent_timeframe: str = "4h"
    primary_timeframe: str = "1d"
    long_term_timeframe: str = "1y"
    default_lookback: int | None = None
    trend_strength: int | None = None
    support_resistance_strength: int | None = None
    volume_average_period: int | None = None
    min_aligned_timeframes: int = 2
    timeframe_weights: Mapping[TimeframeRole, float] = field(
        default_factory=lambda: {
            TimeframeRole.RECENT: 1.0,
            TimeframeRole.PRIMARY: 1.5,
            TimeframeRole.LONG_TERM: 2.0,
            TimeframeRole.SUPPORTING: 1.0,
        }
    )

    def __post_init__(self) -> None:
        """Validate multi-timeframe settings."""
        if self.default_lookback is not None and self.default_lookback <= 1:
            raise ValueError("default_lookback must be greater than one.")
        if self.trend_strength is not None and self.trend_strength <= 0:
            raise ValueError("trend_strength must be greater than zero.")
        if self.support_resistance_strength is not None and self.support_resistance_strength <= 0:
            raise ValueError("support_resistance_strength must be greater than zero.")
        if self.volume_average_period is not None and self.volume_average_period <= 0:
            raise ValueError("volume_average_period must be greater than zero.")
        if self.min_aligned_timeframes <= 0:
            raise ValueError("min_aligned_timeframes must be greater than zero.")
        if any(weight <= 0 for weight in self.timeframe_weights.values()):
            raise ValueError("timeframe_weights must contain positive weights.")


DEFAULT_MULTI_TIMEFRAME_SETTINGS = MultiTimeframeSettings()


@dataclass(frozen=True)
class TimeframeAnalysis:
    """Analysis summary for one candle timeframe."""

    timeframe: str
    role: TimeframeRole
    candles: list[Candle]
    trend: TrendAnalysis
    sideways_market: SidewaysMarketAnalysis
    support_resistance: SupportResistanceAnalysis
    volume: VolumeContext | None
    bias: TimeframeBias
    confidence: float

    @property
    def latest_candle(self) -> Candle | None:
        """Return the latest candle for this timeframe."""
        return self.candles[-1] if self.candles else None


@dataclass(frozen=True)
class MultiTimeframeAnalysis:
    """Combined read across multiple timeframe analyses."""

    timeframes: dict[str, TimeframeAnalysis]
    directional_bias: TimeframeBias
    alignment: MultiTimeframeAlignment
    confidence: float
    conflicts: list[str]

    @property
    def primary(self) -> TimeframeAnalysis | None:
        """Return the primary timeframe analysis when available."""
        return _first_by_role(self.timeframes.values(), TimeframeRole.PRIMARY)

    @property
    def recent(self) -> TimeframeAnalysis | None:
        """Return the recent timeframe analysis when available."""
        return _first_by_role(self.timeframes.values(), TimeframeRole.RECENT)

    @property
    def long_term(self) -> TimeframeAnalysis | None:
        """Return the long-term timeframe analysis when available."""
        return _first_by_role(self.timeframes.values(), TimeframeRole.LONG_TERM)

    @property
    def has_conflicts(self) -> bool:
        """Return whether directional conflicts were detected."""
        return bool(self.conflicts)


def analyze_timeframe(
    timeframe: str,
    candles: Sequence[Candle],
    *,
    role: TimeframeRole = TimeframeRole.SUPPORTING,
    settings: MultiTimeframeSettings = DEFAULT_MULTI_TIMEFRAME_SETTINGS,
) -> TimeframeAnalysis:
    """Analyze one timeframe using existing market-reading helpers."""
    _validate_timeframe_name(timeframe)
    window = list(candles[-settings.default_lookback :] if settings.default_lookback else candles)
    trend = analyze_trend(window, strength=settings.trend_strength)
    sideways_market = analyze_sideways_market(window)
    support_resistance = analyze_support_resistance(
        window,
        strength=settings.support_resistance_strength,
    )
    volume = (
        analyze_volume(
            window,
            average_period=settings.volume_average_period,
            breakout_direction=sideways_market.breakout_direction,
        )
        if window
        else None
    )
    bias = _classify_timeframe_bias(trend, sideways_market, volume)

    return TimeframeAnalysis(
        timeframe=timeframe,
        role=role,
        candles=window,
        trend=trend,
        sideways_market=sideways_market,
        support_resistance=support_resistance,
        volume=volume,
        bias=bias,
        confidence=_timeframe_confidence(trend, sideways_market, volume, bias),
    )


def analyze_multi_timeframe(
    timeframe_candles: Mapping[str, Sequence[Candle]],
    *,
    settings: MultiTimeframeSettings = DEFAULT_MULTI_TIMEFRAME_SETTINGS,
) -> MultiTimeframeAnalysis:
    """Analyze and combine multiple candle timeframes."""
    if not timeframe_candles:
        raise ValueError("timeframe_candles must contain at least one timeframe.")

    analyses = {
        timeframe: analyze_timeframe(
            timeframe,
            candles,
            role=_role_for_timeframe(timeframe, settings),
            settings=settings,
        )
        for timeframe, candles in timeframe_candles.items()
    }
    directional_bias, confidence = _combined_bias_and_confidence(analyses.values(), settings)
    conflicts = _find_conflicts(analyses.values())

    return MultiTimeframeAnalysis(
        timeframes=analyses,
        directional_bias=directional_bias,
        alignment=_classify_alignment(
            analyses.values(),
            directional_bias=directional_bias,
            conflicts=conflicts,
            settings=settings,
        ),
        confidence=confidence,
        conflicts=conflicts,
    )


def _validate_timeframe_name(timeframe: str) -> None:
    if not timeframe.strip():
        raise ValueError("timeframe must not be blank.")


def _role_for_timeframe(timeframe: str, settings: MultiTimeframeSettings) -> TimeframeRole:
    normalized_timeframe = timeframe.casefold()
    if normalized_timeframe == settings.recent_timeframe.casefold():
        return TimeframeRole.RECENT
    if normalized_timeframe == settings.primary_timeframe.casefold():
        return TimeframeRole.PRIMARY
    if normalized_timeframe == settings.long_term_timeframe.casefold():
        return TimeframeRole.LONG_TERM
    return TimeframeRole.SUPPORTING


def _classify_timeframe_bias(
    trend: TrendAnalysis,
    sideways_market: SidewaysMarketAnalysis,
    volume: VolumeContext | None,
) -> TimeframeBias:
    if sideways_market.breakout_direction == BreakoutDirection.UP:
        return TimeframeBias.BULLISH
    if sideways_market.breakout_direction == BreakoutDirection.DOWN:
        return TimeframeBias.BEARISH

    if trend.direction == TrendDirection.UPTREND:
        return TimeframeBias.BULLISH
    if trend.direction == TrendDirection.DOWNTREND:
        return TimeframeBias.BEARISH
    if trend.direction == TrendDirection.SIDEWAYS or sideways_market.is_sideways:
        return TimeframeBias.SIDEWAYS
    if volume and volume.breakout_context == BreakoutVolumeContext.CONFIRMED:
        return TimeframeBias.BULLISH
    return TimeframeBias.UNKNOWN


def _timeframe_confidence(
    trend: TrendAnalysis,
    sideways_market: SidewaysMarketAnalysis,
    volume: VolumeContext | None,
    bias: TimeframeBias,
) -> float:
    if bias == TimeframeBias.UNKNOWN:
        return 0

    base_confidence = max(trend.confidence, sideways_market.confidence)
    if volume and volume.breakout_context == BreakoutVolumeContext.CONFIRMED:
        base_confidence = max(base_confidence, 0.75)
    elif volume and volume.breakout_context == BreakoutVolumeContext.WEAK:
        base_confidence = max(base_confidence * 0.75, 0.25)

    return round(base_confidence, 4)


def _combined_bias_and_confidence(
    analyses: Sequence[TimeframeAnalysis],
    settings: MultiTimeframeSettings,
) -> tuple[TimeframeBias, float]:
    known_analyses = [analysis for analysis in analyses if analysis.bias != TimeframeBias.UNKNOWN]
    if not known_analyses:
        return TimeframeBias.UNKNOWN, 0

    weighted_scores = {
        TimeframeBias.BULLISH: 0.0,
        TimeframeBias.BEARISH: 0.0,
        TimeframeBias.SIDEWAYS: 0.0,
    }
    weighted_confidence = 0.0
    total_weight = 0.0

    for analysis in known_analyses:
        weight = settings.timeframe_weights[analysis.role]
        weighted_scores[analysis.bias] += weight
        weighted_confidence += analysis.confidence * weight
        total_weight += weight

    highest_score = max(weighted_scores.values())
    winning_biases = [bias for bias, score in weighted_scores.items() if score == highest_score]
    if len(winning_biases) != 1:
        return TimeframeBias.UNKNOWN, 0

    agreement_ratio = highest_score / total_weight
    confidence = weighted_confidence / total_weight * agreement_ratio
    return winning_biases[0], round(confidence, 4)


def _find_conflicts(analyses: Sequence[TimeframeAnalysis]) -> list[str]:
    directional_analyses = [
        analysis
        for analysis in analyses
        if analysis.bias in {TimeframeBias.BULLISH, TimeframeBias.BEARISH}
    ]
    conflicts: list[str] = []

    for index, first in enumerate(directional_analyses):
        for second in directional_analyses[index + 1 :]:
            if first.bias != second.bias:
                conflicts.append(
                    f"{first.timeframe} is {first.bias}; {second.timeframe} is {second.bias}"
                )

    return conflicts


def _classify_alignment(
    analyses: Sequence[TimeframeAnalysis],
    *,
    directional_bias: TimeframeBias,
    conflicts: Sequence[str],
    settings: MultiTimeframeSettings,
) -> MultiTimeframeAlignment:
    known_biases = [
        analysis.bias for analysis in analyses if analysis.bias != TimeframeBias.UNKNOWN
    ]
    if len(known_biases) < settings.min_aligned_timeframes:
        return MultiTimeframeAlignment.UNKNOWN
    if conflicts:
        return MultiTimeframeAlignment.CONFLICTED
    if all(bias == TimeframeBias.SIDEWAYS for bias in known_biases):
        return MultiTimeframeAlignment.SIDEWAYS

    aligned_count = sum(bias == directional_bias for bias in known_biases)
    all_known_aligned = aligned_count == len(known_biases)

    if directional_bias == TimeframeBias.BULLISH:
        return (
            MultiTimeframeAlignment.STRONG_BULLISH
            if all_known_aligned
            else MultiTimeframeAlignment.BULLISH
        )
    if directional_bias == TimeframeBias.BEARISH:
        return (
            MultiTimeframeAlignment.STRONG_BEARISH
            if all_known_aligned
            else MultiTimeframeAlignment.BEARISH
        )
    if directional_bias == TimeframeBias.SIDEWAYS:
        return MultiTimeframeAlignment.SIDEWAYS
    return MultiTimeframeAlignment.UNKNOWN


def _first_by_role(
    analyses: Sequence[TimeframeAnalysis],
    role: TimeframeRole,
) -> TimeframeAnalysis | None:
    return next((analysis for analysis in analyses if analysis.role == role), None)
