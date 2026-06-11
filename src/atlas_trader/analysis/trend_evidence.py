"""Report-only trend evidence helpers."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from atlas_trader.analysis.moving_averages import (
    MovingAveragePosition,
    MovingAverageReportContext,
)
from atlas_trader.analysis.ranges import (
    BreakoutDirection,
    SidewaysMarketAnalysis,
    SidewaysMarketType,
)
from atlas_trader.analysis.trend_health import ShortTermPressure, TrendHealthContext
from atlas_trader.analysis.trends import TrendAnalysis, TrendDirection
from atlas_trader.data.models import Candle


class TrendFallbackReason(StrEnum):
    """Reason the clean swing-structure trend did not resolve directionally."""

    INSUFFICIENT_SWING_STRUCTURE = "insufficient_swing_structure"
    MIXED_SWING_STRUCTURE = "mixed_swing_structure"
    LOW_CONFIDENCE_SWING_STRUCTURE = "low_confidence_swing_structure"
    NOT_SIDEWAYS = "not_sideways"


class TrendCandidateBlockedReason(StrEnum):
    """Reason a directional report-only candidate was blocked."""

    RANGE_MARKET_WITHOUT_BREAKOUT_EVIDENCE = "range_market_without_breakout_evidence"


@dataclass(frozen=True)
class TrendEvidenceSettings:
    """Tunable settings for report-only trend evidence."""

    directional_window_return_threshold: float = 0.03
    range_market_window_return_threshold: float = 0.06
    candidate_score_threshold: int = 3
    range_market_candidate_score_threshold: int = 4
    swing_bias_ratio: float = 0.60

    def __post_init__(self) -> None:
        """Validate trend-evidence settings."""
        if self.directional_window_return_threshold < 0:
            raise ValueError("directional_window_return_threshold cannot be negative.")
        if self.range_market_window_return_threshold < self.directional_window_return_threshold:
            raise ValueError(
                "range_market_window_return_threshold cannot be less than "
                "directional_window_return_threshold."
            )
        if self.candidate_score_threshold <= 0:
            raise ValueError("candidate_score_threshold must be greater than zero.")
        if self.range_market_candidate_score_threshold < self.candidate_score_threshold:
            raise ValueError(
                "range_market_candidate_score_threshold cannot be less than "
                "candidate_score_threshold."
            )
        if not 0 <= self.swing_bias_ratio <= 1:
            raise ValueError("swing_bias_ratio must be between zero and one.")


DEFAULT_TREND_EVIDENCE_SETTINGS = TrendEvidenceSettings()


@dataclass(frozen=True)
class TrendEvidenceContext:
    """Report-only evidence explaining structural trend decisions."""

    confirmed_swing_high_count: int
    confirmed_swing_low_count: int
    higher_high_ratio: float | None
    higher_low_ratio: float | None
    lower_high_ratio: float | None
    lower_low_ratio: float | None
    trend_fallback_reason: TrendFallbackReason | None
    insufficient_swing_structure: bool
    trend_candidate: TrendDirection
    trend_candidate_confidence: float
    trend_candidate_score: int
    trend_candidate_direction_score: int
    trend_candidate_conflict_count: int
    trend_candidate_blocked_reason: TrendCandidateBlockedReason | None
    trend_candidate_raw_reasons: list[str]
    trend_candidate_reasons: list[str]
    trend_candidate_conflicts: list[str]
    messy_trend_candidate: bool
    messy_trend_direction: str
    window_return_pct: float | None


def analyze_trend_evidence(
    candles: Sequence[Candle],
    *,
    trend: TrendAnalysis,
    sideways_market: SidewaysMarketAnalysis,
    moving_average_context: MovingAverageReportContext,
    trend_health: TrendHealthContext,
    settings: TrendEvidenceSettings = DEFAULT_TREND_EVIDENCE_SETTINGS,
) -> TrendEvidenceContext:
    """Build report-only evidence around the clean swing-structure trend."""
    higher_high_ratio = _ratio(
        trend.higher_high_count,
        trend.higher_high_count + trend.lower_high_count + trend.equal_high_count,
    )
    higher_low_ratio = _ratio(
        trend.higher_low_count,
        trend.higher_low_count + trend.lower_low_count + trend.equal_low_count,
    )
    lower_high_ratio = _ratio(
        trend.lower_high_count,
        trend.higher_high_count + trend.lower_high_count + trend.equal_high_count,
    )
    lower_low_ratio = _ratio(
        trend.lower_low_count,
        trend.higher_low_count + trend.lower_low_count + trend.equal_low_count,
    )
    window_return_pct = _window_return_pct(candles)
    insufficient_swing_structure = not trend.swing_highs or not trend.swing_lows

    candidate_result = _candidate_from_evidence(
        window_return_pct=window_return_pct,
        higher_high_ratio=higher_high_ratio,
        higher_low_ratio=higher_low_ratio,
        lower_high_ratio=lower_high_ratio,
        lower_low_ratio=lower_low_ratio,
        sideways_market=sideways_market,
        moving_average_context=moving_average_context,
        trend_health=trend_health,
        settings=settings,
    )
    messy_trend_candidate = (
        candidate_result.candidate in {TrendDirection.UPTREND, TrendDirection.DOWNTREND}
        and trend.direction != candidate_result.candidate
    )

    return TrendEvidenceContext(
        confirmed_swing_high_count=len(trend.swing_highs),
        confirmed_swing_low_count=len(trend.swing_lows),
        higher_high_ratio=higher_high_ratio,
        higher_low_ratio=higher_low_ratio,
        lower_high_ratio=lower_high_ratio,
        lower_low_ratio=lower_low_ratio,
        trend_fallback_reason=_fallback_reason(
            trend,
            insufficient_swing_structure=insufficient_swing_structure,
        ),
        insufficient_swing_structure=insufficient_swing_structure,
        trend_candidate=candidate_result.candidate,
        trend_candidate_confidence=candidate_result.confidence,
        trend_candidate_score=candidate_result.score,
        trend_candidate_direction_score=candidate_result.direction_score,
        trend_candidate_conflict_count=len(candidate_result.conflicts),
        trend_candidate_blocked_reason=candidate_result.blocked_reason,
        trend_candidate_raw_reasons=candidate_result.raw_reasons,
        trend_candidate_reasons=candidate_result.reasons,
        trend_candidate_conflicts=candidate_result.conflicts,
        messy_trend_candidate=messy_trend_candidate,
        messy_trend_direction=_messy_direction(
            candidate_result.candidate,
            messy_trend_candidate,
        ),
        window_return_pct=window_return_pct,
    )


@dataclass(frozen=True)
class _TrendCandidateResult:
    candidate: TrendDirection
    confidence: float
    score: int
    direction_score: int
    blocked_reason: TrendCandidateBlockedReason | None
    raw_reasons: list[str]
    reasons: list[str]
    conflicts: list[str]


def _candidate_from_evidence(
    *,
    window_return_pct: float | None,
    higher_high_ratio: float | None,
    higher_low_ratio: float | None,
    lower_high_ratio: float | None,
    lower_low_ratio: float | None,
    sideways_market: SidewaysMarketAnalysis,
    moving_average_context: MovingAverageReportContext,
    trend_health: TrendHealthContext,
    settings: TrendEvidenceSettings,
) -> _TrendCandidateResult:
    up_reasons: list[str] = []
    down_reasons: list[str] = []

    if window_return_pct is not None:
        if window_return_pct >= settings.directional_window_return_threshold:
            up_reasons.append("positive_window_return")
        elif window_return_pct <= -settings.directional_window_return_threshold:
            down_reasons.append("negative_window_return")

    _add_swing_bias_reasons(
        up_reasons=up_reasons,
        down_reasons=down_reasons,
        higher_high_ratio=higher_high_ratio,
        higher_low_ratio=higher_low_ratio,
        lower_high_ratio=lower_high_ratio,
        lower_low_ratio=lower_low_ratio,
        settings=settings,
    )
    _add_ma_reasons(up_reasons, down_reasons, moving_average_context)
    _add_pressure_reasons(up_reasons, down_reasons, trend_health)

    up_score = len(up_reasons)
    down_score = len(down_reasons)
    total_score = up_score + down_score
    raw_reasons = _raw_reasons(up_reasons=up_reasons, down_reasons=down_reasons)
    if total_score == 0:
        return _TrendCandidateResult(
            candidate=TrendDirection.UNKNOWN,
            confidence=0,
            score=0,
            direction_score=0,
            blocked_reason=None,
            raw_reasons=[],
            reasons=[],
            conflicts=[],
        )

    leading_direction = _leading_direction(up_score=up_score, down_score=down_score)
    direction_reasons = _direction_reasons(
        leading_direction,
        up_reasons=up_reasons,
        down_reasons=down_reasons,
    )
    conflicts = _candidate_conflicts(
        leading_direction,
        up_reasons=up_reasons,
        down_reasons=down_reasons,
    )
    direction_score = max(up_score, down_score)
    adjusted_score = max(0, direction_score - len(conflicts))

    blocked_reason = _blocked_reason(
        leading_direction=leading_direction,
        adjusted_score=adjusted_score,
        window_return_pct=window_return_pct,
        sideways_market=sideways_market,
        trend_health=trend_health,
        settings=settings,
    )
    if blocked_reason is not None:
        return _TrendCandidateResult(
            candidate=TrendDirection.SIDEWAYS,
            confidence=adjusted_score / total_score,
            score=0,
            direction_score=direction_score,
            blocked_reason=blocked_reason,
            raw_reasons=raw_reasons,
            reasons=direction_reasons,
            conflicts=conflicts,
        )

    if up_score >= settings.candidate_score_threshold and up_score > down_score:
        return _TrendCandidateResult(
            candidate=TrendDirection.UPTREND,
            confidence=adjusted_score / total_score,
            score=adjusted_score,
            direction_score=direction_score,
            blocked_reason=None,
            raw_reasons=raw_reasons,
            reasons=up_reasons,
            conflicts=conflicts,
        )
    if down_score >= settings.candidate_score_threshold and down_score > up_score:
        return _TrendCandidateResult(
            candidate=TrendDirection.DOWNTREND,
            confidence=adjusted_score / total_score,
            score=adjusted_score,
            direction_score=direction_score,
            blocked_reason=None,
            raw_reasons=raw_reasons,
            reasons=down_reasons,
            conflicts=conflicts,
        )
    if up_score == down_score:
        return _TrendCandidateResult(
            candidate=TrendDirection.SIDEWAYS,
            confidence=0.5,
            score=adjusted_score,
            direction_score=direction_score,
            blocked_reason=None,
            raw_reasons=raw_reasons,
            reasons=[*up_reasons, *down_reasons],
            conflicts=conflicts,
        )
    return _TrendCandidateResult(
        candidate=TrendDirection.SIDEWAYS,
        confidence=adjusted_score / total_score,
        score=adjusted_score,
        direction_score=direction_score,
        blocked_reason=None,
        raw_reasons=raw_reasons,
        reasons=[*up_reasons, *down_reasons],
        conflicts=conflicts,
    )


def _add_swing_bias_reasons(
    *,
    up_reasons: list[str],
    down_reasons: list[str],
    higher_high_ratio: float | None,
    higher_low_ratio: float | None,
    lower_high_ratio: float | None,
    lower_low_ratio: float | None,
    settings: TrendEvidenceSettings,
) -> None:
    if higher_high_ratio is not None and higher_high_ratio >= settings.swing_bias_ratio:
        up_reasons.append("higher_highs_partial")
    if higher_low_ratio is not None and higher_low_ratio >= settings.swing_bias_ratio:
        up_reasons.append("higher_lows_partial")
    if lower_high_ratio is not None and lower_high_ratio >= settings.swing_bias_ratio:
        down_reasons.append("lower_highs_partial")
    if lower_low_ratio is not None and lower_low_ratio >= settings.swing_bias_ratio:
        down_reasons.append("lower_lows_partial")


def _add_ma_reasons(
    up_reasons: list[str],
    down_reasons: list[str],
    moving_average_context: MovingAverageReportContext,
) -> None:
    if moving_average_context.ema_50.position in {
        MovingAveragePosition.ABOVE,
        MovingAveragePosition.NEAR,
    }:
        up_reasons.append("price_above_or_near_ema50")
    elif moving_average_context.ema_50.position == MovingAveragePosition.BELOW:
        down_reasons.append("price_below_ema50")

    if moving_average_context.ema_200.position == MovingAveragePosition.ABOVE:
        up_reasons.append("price_above_ema200")
    elif moving_average_context.ema_200.position == MovingAveragePosition.BELOW:
        down_reasons.append("price_below_ema200")


def _add_pressure_reasons(
    up_reasons: list[str],
    down_reasons: list[str],
    trend_health: TrendHealthContext,
) -> None:
    if trend_health.short_term_pressure == ShortTermPressure.BULLISH:
        up_reasons.append("bullish_pressure")
    elif trend_health.short_term_pressure == ShortTermPressure.BEARISH:
        down_reasons.append("bearish_pressure")

    if "recent_higher_closes" in trend_health.trend_health_reasons:
        up_reasons.append("recent_higher_closes")
    if "recent_lower_closes" in trend_health.trend_health_reasons:
        down_reasons.append("recent_lower_closes")


def _raw_reasons(*, up_reasons: list[str], down_reasons: list[str]) -> list[str]:
    return [
        *(f"up:{reason}" for reason in up_reasons),
        *(f"down:{reason}" for reason in down_reasons),
    ]


def _leading_direction(*, up_score: int, down_score: int) -> TrendDirection:
    if up_score > down_score:
        return TrendDirection.UPTREND
    if down_score > up_score:
        return TrendDirection.DOWNTREND
    if up_score == 0:
        return TrendDirection.UNKNOWN
    return TrendDirection.SIDEWAYS


def _direction_reasons(
    direction: TrendDirection,
    *,
    up_reasons: list[str],
    down_reasons: list[str],
) -> list[str]:
    if direction == TrendDirection.UPTREND:
        return up_reasons
    if direction == TrendDirection.DOWNTREND:
        return down_reasons
    return [*up_reasons, *down_reasons]


def _candidate_conflicts(
    direction: TrendDirection,
    *,
    up_reasons: list[str],
    down_reasons: list[str],
) -> list[str]:
    if direction == TrendDirection.UPTREND:
        return [
            _conflict_reason(reason)
            for reason in down_reasons
            if reason in {"bearish_pressure", "recent_lower_closes"}
        ]
    if direction == TrendDirection.DOWNTREND:
        return [
            _conflict_reason(reason)
            for reason in up_reasons
            if reason in {"bullish_pressure", "recent_higher_closes"}
        ]
    return []


def _conflict_reason(reason: str) -> str:
    return f"{reason}_conflict"


def _blocked_reason(
    *,
    leading_direction: TrendDirection,
    adjusted_score: int,
    window_return_pct: float | None,
    sideways_market: SidewaysMarketAnalysis,
    trend_health: TrendHealthContext,
    settings: TrendEvidenceSettings,
) -> TrendCandidateBlockedReason | None:
    if leading_direction not in {TrendDirection.UPTREND, TrendDirection.DOWNTREND}:
        return None
    if sideways_market.market_type not in {
        SidewaysMarketType.TRADING_RANGE,
        SidewaysMarketType.CONSOLIDATION,
        SidewaysMarketType.CONGESTION,
    }:
        return None
    if _has_directional_breakout(
        leading_direction=leading_direction,
        breakout_direction=sideways_market.breakout_direction,
    ):
        return None
    if _has_strong_range_market_evidence(
        leading_direction=leading_direction,
        adjusted_score=adjusted_score,
        window_return_pct=window_return_pct,
        trend_health=trend_health,
        settings=settings,
    ):
        return None
    return TrendCandidateBlockedReason.RANGE_MARKET_WITHOUT_BREAKOUT_EVIDENCE


def _has_directional_breakout(
    *,
    leading_direction: TrendDirection,
    breakout_direction: BreakoutDirection,
) -> bool:
    return (
        leading_direction == TrendDirection.UPTREND and breakout_direction == BreakoutDirection.UP
    ) or (
        leading_direction == TrendDirection.DOWNTREND
        and breakout_direction == BreakoutDirection.DOWN
    )


def _has_strong_range_market_evidence(
    *,
    leading_direction: TrendDirection,
    adjusted_score: int,
    window_return_pct: float | None,
    trend_health: TrendHealthContext,
    settings: TrendEvidenceSettings,
) -> bool:
    if adjusted_score < settings.range_market_candidate_score_threshold:
        return False
    if window_return_pct is None:
        return False
    if abs(window_return_pct) < settings.range_market_window_return_threshold:
        return False
    if leading_direction == TrendDirection.UPTREND:
        return trend_health.short_term_pressure == ShortTermPressure.BULLISH
    if leading_direction == TrendDirection.DOWNTREND:
        return trend_health.short_term_pressure == ShortTermPressure.BEARISH
    return False


def _fallback_reason(
    trend: TrendAnalysis,
    *,
    insufficient_swing_structure: bool,
) -> TrendFallbackReason | None:
    if trend.direction not in {TrendDirection.SIDEWAYS, TrendDirection.UNKNOWN}:
        return None
    if insufficient_swing_structure:
        return TrendFallbackReason.INSUFFICIENT_SWING_STRUCTURE
    if trend.direction == TrendDirection.UNKNOWN:
        return TrendFallbackReason.INSUFFICIENT_SWING_STRUCTURE
    if trend.confidence < 0.75:
        return TrendFallbackReason.LOW_CONFIDENCE_SWING_STRUCTURE
    return TrendFallbackReason.MIXED_SWING_STRUCTURE


def _window_return_pct(candles: Sequence[Candle]) -> float | None:
    if len(candles) < 2 or candles[0].close <= 0:
        return None
    return (candles[-1].close - candles[0].close) / candles[0].close


def _ratio(count: int, total: int) -> float | None:
    if total <= 0:
        return None
    return count / total


def _messy_direction(candidate: TrendDirection, messy_trend_candidate: bool) -> str:
    if not messy_trend_candidate:
        return "unknown"
    if candidate == TrendDirection.UPTREND:
        return "up"
    if candidate == TrendDirection.DOWNTREND:
        return "down"
    return "unknown"
