"""Tests for report-only trend evidence helpers."""

from datetime import datetime, timedelta

from atlas_trader.analysis.moving_averages import (
    MovingAverageLevel,
    MovingAveragePosition,
    MovingAverageReportContext,
)
from atlas_trader.analysis.ranges import (
    BreakoutDirection,
    SidewaysMarketAnalysis,
    SidewaysMarketType,
)
from atlas_trader.analysis.trend_evidence import analyze_trend_evidence
from atlas_trader.analysis.trend_health import (
    ShortTermPressure,
    TrendCondition,
    TrendHealthContext,
)
from atlas_trader.analysis.trends import TrendAnalysis, TrendDirection
from atlas_trader.data.models import Candle


def make_candle(index: int, close: float) -> Candle:
    return Candle(
        symbol="TEST",
        timestamp=datetime(2026, 1, 1) + timedelta(days=index),
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=1000,
    )


def non_sideways_market() -> SidewaysMarketAnalysis:
    return SidewaysMarketAnalysis(
        market_type=SidewaysMarketType.NOT_SIDEWAYS,
        upper_bound=130,
        lower_bound=100,
        midpoint=115,
        height=30,
        height_pct=30 / 115,
        close_drift=20,
        close_drift_ratio=20 / 30,
        average_candle_range=2,
        average_candle_range_pct=2 / 115,
        support_touches=0,
        resistance_touches=0,
        breakout_direction=BreakoutDirection.NONE,
        confidence=0,
    )


def moving_average_context() -> MovingAverageReportContext:
    ema_50 = MovingAverageLevel(
        name="EMA50",
        period=50,
        value=110,
        position=MovingAveragePosition.ABOVE,
        distance_from_close=10,
        distance_from_close_pct=10 / 120,
    )
    return MovingAverageReportContext(
        ema_20=MovingAverageLevel(
            name="EMA20",
            period=20,
            value=None,
            position=MovingAveragePosition.UNKNOWN,
            distance_from_close=None,
            distance_from_close_pct=None,
        ),
        ema_50=ema_50,
        ema_200=MovingAverageLevel(
            name="EMA200",
            period=200,
            value=None,
            position=MovingAveragePosition.UNKNOWN,
            distance_from_close=None,
            distance_from_close_pct=None,
        ),
        nearest_ma_support=ema_50,
        nearest_ma_resistance=None,
    )


def bearish_pressure_context() -> TrendHealthContext:
    return TrendHealthContext(
        short_term_pressure=ShortTermPressure.BEARISH,
        trend_condition=TrendCondition.PULLING_BACK,
        recent_return_pct=-0.02,
        consecutive_down_closes=3,
        consecutive_up_closes=0,
        pullback_from_recent_high_pct=0.04,
        bounce_from_recent_low_pct=0,
        trend_health_reasons=["bearish_pressure"],
    )


def partial_uptrend_structure() -> TrendAnalysis:
    return TrendAnalysis(
        direction=TrendDirection.SIDEWAYS,
        confidence=0.5,
        swing_highs=[],
        swing_lows=[],
        higher_high_count=1,
        higher_low_count=0,
        lower_high_count=0,
        lower_low_count=0,
        equal_high_count=0,
        equal_low_count=0,
    )


def test_candidate_conflict_adjusted_score_below_threshold_blocks_direction() -> None:
    context = analyze_trend_evidence(
        [make_candle(0, 100), make_candle(1, 120)],
        trend=partial_uptrend_structure(),
        sideways_market=non_sideways_market(),
        moving_average_context=moving_average_context(),
        trend_health=bearish_pressure_context(),
    )

    assert context.trend_candidate == TrendDirection.SIDEWAYS
    assert context.trend_candidate_raw_score == 3
    assert context.trend_candidate_conflict_count == 1
    assert context.trend_candidate_effective_score == 2
    assert context.trend_candidate_threshold == 3
    assert context.trend_candidate_selected_score == 0
    assert context.trend_candidate_blocked_reason == ("conflict_adjusted_score_below_threshold")
    assert context.trend_candidate_conflicts == ["bearish_pressure_conflict"]
    assert context.trend_candidate_raw_reasons == [
        "up:positive_window_return",
        "up:higher_highs_partial",
        "up:price_above_or_near_ema50",
        "down:bearish_pressure",
    ]
