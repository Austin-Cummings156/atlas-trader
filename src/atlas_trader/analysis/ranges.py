"""Sideways market, range, consolidation, and congestion analysis helpers."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from statistics import fmean

from atlas_trader.data.models import Candle

DEFAULT_BOUNDARY_TOLERANCE_RATIO = 0.15
DEFAULT_MAX_SIDEWAYS_HEIGHT_PCT = 0.18
DEFAULT_MAX_CONSOLIDATION_HEIGHT_PCT = 0.10
DEFAULT_MAX_CONGESTION_HEIGHT_PCT = 0.04
DEFAULT_MAX_SIDEWAYS_DRIFT_RATIO = 0.60
DEFAULT_MIN_BOUNDARY_TOUCHES = 2


class SidewaysMarketType(StrEnum):
    """Specific type of sideways price action."""

    TRADING_RANGE = "trading_range"
    CONSOLIDATION = "consolidation"
    CONGESTION = "congestion"
    NOT_SIDEWAYS = "not_sideways"
    UNKNOWN = "unknown"


class BreakoutDirection(StrEnum):
    """Direction of a close outside the detected range."""

    UP = "up"
    DOWN = "down"
    NONE = "none"


@dataclass(frozen=True)
class SidewaysMarketAnalysis:
    """Summary of sideways structure over a candle window."""

    market_type: SidewaysMarketType
    upper_bound: float | None
    lower_bound: float | None
    midpoint: float | None
    height: float | None
    height_pct: float | None
    close_drift: float | None
    close_drift_ratio: float | None
    average_candle_range: float | None
    average_candle_range_pct: float | None
    support_touches: int
    resistance_touches: int
    breakout_direction: BreakoutDirection
    confidence: float

    @property
    def is_sideways(self) -> bool:
        """Return whether the window is classified as sideways price action."""
        return self.market_type in {
            SidewaysMarketType.TRADING_RANGE,
            SidewaysMarketType.CONSOLIDATION,
            SidewaysMarketType.CONGESTION,
        }


def analyze_sideways_market(
    candles: Sequence[Candle],
    *,
    lookback: int | None = None,
    boundary_tolerance_ratio: float = DEFAULT_BOUNDARY_TOLERANCE_RATIO,
    max_sideways_height_pct: float = DEFAULT_MAX_SIDEWAYS_HEIGHT_PCT,
    max_consolidation_height_pct: float = DEFAULT_MAX_CONSOLIDATION_HEIGHT_PCT,
    max_congestion_height_pct: float = DEFAULT_MAX_CONGESTION_HEIGHT_PCT,
    max_sideways_drift_ratio: float = DEFAULT_MAX_SIDEWAYS_DRIFT_RATIO,
    min_boundary_touches: int = DEFAULT_MIN_BOUNDARY_TOUCHES,
) -> SidewaysMarketAnalysis:
    """Classify a candle window as trading range, consolidation, congestion, or directional.

    The rules are deliberately simple for v0.3:
    - trading range: repeated support and resistance touches inside a bounded band
    - congestion: a very tight overlapping band with limited close-to-close drift
    - consolidation: a bounded sideways pause that is wider than congestion and lacks range touches
    """
    _validate_inputs(
        lookback=lookback,
        boundary_tolerance_ratio=boundary_tolerance_ratio,
        max_sideways_height_pct=max_sideways_height_pct,
        max_consolidation_height_pct=max_consolidation_height_pct,
        max_congestion_height_pct=max_congestion_height_pct,
        max_sideways_drift_ratio=max_sideways_drift_ratio,
        min_boundary_touches=min_boundary_touches,
    )

    window = list(candles[-lookback:] if lookback is not None else candles)
    if len(window) < 2:
        return _unknown_analysis()

    upper_bound = max(candle.high for candle in window)
    lower_bound = min(candle.low for candle in window)
    height = upper_bound - lower_bound
    midpoint = (upper_bound + lower_bound) / 2

    if height <= 0 or midpoint <= 0:
        return _unknown_analysis()

    height_pct = height / midpoint
    close_drift = window[-1].close - window[0].close
    close_drift_ratio = abs(close_drift) / height
    candle_ranges = [candle.high - candle.low for candle in window]
    average_candle_range = fmean(candle_ranges)
    average_candle_range_pct = average_candle_range / midpoint

    tolerance = height * boundary_tolerance_ratio
    support_touches = sum(candle.low <= lower_bound + tolerance for candle in window)
    resistance_touches = sum(candle.high >= upper_bound - tolerance for candle in window)
    breakout_direction = _classify_breakout(window, tolerance)

    market_type = _classify_sideways_type(
        height_pct=height_pct,
        close_drift_ratio=close_drift_ratio,
        support_touches=support_touches,
        resistance_touches=resistance_touches,
        average_candle_range_pct=average_candle_range_pct,
        max_sideways_height_pct=max_sideways_height_pct,
        max_consolidation_height_pct=max_consolidation_height_pct,
        max_congestion_height_pct=max_congestion_height_pct,
        max_sideways_drift_ratio=max_sideways_drift_ratio,
        min_boundary_touches=min_boundary_touches,
    )

    return SidewaysMarketAnalysis(
        market_type=market_type,
        upper_bound=upper_bound,
        lower_bound=lower_bound,
        midpoint=midpoint,
        height=height,
        height_pct=height_pct,
        close_drift=close_drift,
        close_drift_ratio=close_drift_ratio,
        average_candle_range=average_candle_range,
        average_candle_range_pct=average_candle_range_pct,
        support_touches=support_touches,
        resistance_touches=resistance_touches,
        breakout_direction=breakout_direction,
        confidence=_confidence_for(
            market_type=market_type,
            height_pct=height_pct,
            close_drift_ratio=close_drift_ratio,
            support_touches=support_touches,
            resistance_touches=resistance_touches,
            max_sideways_height_pct=max_sideways_height_pct,
            max_sideways_drift_ratio=max_sideways_drift_ratio,
            min_boundary_touches=min_boundary_touches,
        ),
    )


def _validate_inputs(
    *,
    lookback: int | None,
    boundary_tolerance_ratio: float,
    max_sideways_height_pct: float,
    max_consolidation_height_pct: float,
    max_congestion_height_pct: float,
    max_sideways_drift_ratio: float,
    min_boundary_touches: int,
) -> None:
    if lookback is not None and lookback <= 1:
        raise ValueError("lookback must be greater than one.")
    if boundary_tolerance_ratio < 0:
        raise ValueError("boundary_tolerance_ratio cannot be negative.")
    if min_boundary_touches <= 0:
        raise ValueError("min_boundary_touches must be greater than zero.")
    if max_sideways_drift_ratio < 0:
        raise ValueError("max_sideways_drift_ratio cannot be negative.")
    if not 0 < max_congestion_height_pct <= max_consolidation_height_pct <= max_sideways_height_pct:
        raise ValueError(
            "height thresholds must satisfy 0 < congestion <= consolidation <= sideways."
        )


def _unknown_analysis() -> SidewaysMarketAnalysis:
    return SidewaysMarketAnalysis(
        market_type=SidewaysMarketType.UNKNOWN,
        upper_bound=None,
        lower_bound=None,
        midpoint=None,
        height=None,
        height_pct=None,
        close_drift=None,
        close_drift_ratio=None,
        average_candle_range=None,
        average_candle_range_pct=None,
        support_touches=0,
        resistance_touches=0,
        breakout_direction=BreakoutDirection.NONE,
        confidence=0,
    )


def _classify_breakout(window: Sequence[Candle], tolerance: float) -> BreakoutDirection:
    if len(window) < 3:
        return BreakoutDirection.NONE

    latest_candle = window[-1]
    prior_candles = window[:-1]
    prior_upper_bound = max(candle.high for candle in prior_candles)
    prior_lower_bound = min(candle.low for candle in prior_candles)

    if latest_candle.close > prior_upper_bound + tolerance:
        return BreakoutDirection.UP

    if latest_candle.close < prior_lower_bound - tolerance:
        return BreakoutDirection.DOWN

    return BreakoutDirection.NONE


def _classify_sideways_type(
    *,
    height_pct: float,
    close_drift_ratio: float,
    support_touches: int,
    resistance_touches: int,
    average_candle_range_pct: float,
    max_sideways_height_pct: float,
    max_consolidation_height_pct: float,
    max_congestion_height_pct: float,
    max_sideways_drift_ratio: float,
    min_boundary_touches: int,
) -> SidewaysMarketType:
    if height_pct > max_sideways_height_pct or close_drift_ratio > max_sideways_drift_ratio:
        return SidewaysMarketType.NOT_SIDEWAYS

    has_range_touches = (
        support_touches >= min_boundary_touches and resistance_touches >= min_boundary_touches
    )
    if (
        height_pct <= max_congestion_height_pct
        and average_candle_range_pct <= max_congestion_height_pct / 2
    ):
        return SidewaysMarketType.CONGESTION

    if has_range_touches:
        return SidewaysMarketType.TRADING_RANGE

    if height_pct <= max_consolidation_height_pct:
        return SidewaysMarketType.CONSOLIDATION

    return SidewaysMarketType.NOT_SIDEWAYS


def _confidence_for(
    *,
    market_type: SidewaysMarketType,
    height_pct: float,
    close_drift_ratio: float,
    support_touches: int,
    resistance_touches: int,
    max_sideways_height_pct: float,
    max_sideways_drift_ratio: float,
    min_boundary_touches: int,
) -> float:
    if market_type in {SidewaysMarketType.UNKNOWN, SidewaysMarketType.NOT_SIDEWAYS}:
        return 0

    height_score = max(0.0, 1 - height_pct / max_sideways_height_pct)
    drift_score = max(0.0, 1 - close_drift_ratio / max_sideways_drift_ratio)
    touch_score = min(support_touches, resistance_touches) / min_boundary_touches
    touch_score = min(touch_score, 1.0)

    if market_type == SidewaysMarketType.TRADING_RANGE:
        return round((height_score + drift_score + touch_score) / 3, 4)

    return round((height_score + drift_score) / 2, 4)
