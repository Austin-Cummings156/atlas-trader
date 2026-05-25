"""Tests for trend and swing-structure helpers."""

from datetime import datetime, timedelta

import pytest

import atlas_trader.analysis as analysis_api
from atlas_trader.analysis.trends import (
    SwingPointType,
    TrendDirection,
    analyze_trend,
    find_swing_highs,
    find_swing_lows,
    find_swing_points,
)
from atlas_trader.data.models import Candle


def make_candle(index: int, *, high: float, low: float, close: float | None = None) -> Candle:
    close_price = close if close is not None else (high + low) / 2
    return Candle(
        symbol="BTC-USD",
        timestamp=datetime(2026, 1, 1) + timedelta(days=index),
        open=close_price,
        high=high,
        low=low,
        close=close_price,
        volume=1000,
    )


def test_trend_api_is_exposed_from_analysis_package() -> None:
    assert analysis_api.TrendAnalysis is not None
    assert analysis_api.analyze_trend is analyze_trend


def test_find_swing_points_uses_confirming_candles_on_both_sides() -> None:
    candles = [
        make_candle(0, high=10, low=8),
        make_candle(1, high=12, low=7),
        make_candle(2, high=11, low=9),
        make_candle(3, high=13, low=10),
        make_candle(4, high=12, low=11),
    ]

    swing_points = find_swing_points(candles, strength=1)

    assert [(point.index, point.point_type, point.price) for point in swing_points] == [
        (1, SwingPointType.HIGH, 12),
        (1, SwingPointType.LOW, 7),
        (3, SwingPointType.HIGH, 13),
    ]


def test_analyze_uptrend_from_higher_highs_and_higher_lows() -> None:
    candles = [
        make_candle(0, high=10, low=7),
        make_candle(1, high=14, low=10),
        make_candle(2, high=11, low=9),
        make_candle(3, high=16, low=12),
        make_candle(4, high=13, low=10.5),
        make_candle(5, high=18, low=13),
        make_candle(6, high=15, low=13),
    ]

    trend = analyze_trend(candles, strength=1)

    assert trend.direction == TrendDirection.UPTREND
    assert trend.higher_high_count == 2
    assert trend.higher_low_count == 1
    assert trend.confidence == pytest.approx(1)
    assert trend.latest_swing_high == trend.swing_highs[-1]
    assert trend.latest_swing_low == trend.swing_lows[-1]


def test_analyze_downtrend_from_lower_highs_and_lower_lows() -> None:
    candles = [
        make_candle(0, high=20, low=17),
        make_candle(1, high=24, low=18),
        make_candle(2, high=21, low=14),
        make_candle(3, high=22, low=15),
        make_candle(4, high=19, low=12),
        make_candle(5, high=20, low=13),
        make_candle(6, high=17, low=10),
    ]

    trend = analyze_trend(candles, strength=1)

    assert trend.direction == TrendDirection.DOWNTREND
    assert trend.lower_high_count == 2
    assert trend.lower_low_count == 1
    assert trend.confidence == pytest.approx(1)


def test_analyze_trend_returns_sideways_for_mixed_structure() -> None:
    candles = [
        make_candle(0, high=10, low=7),
        make_candle(1, high=14, low=8),
        make_candle(2, high=11, low=6),
        make_candle(3, high=13, low=9),
        make_candle(4, high=10, low=5),
        make_candle(5, high=15, low=8),
        make_candle(6, high=12, low=6),
    ]

    trend = analyze_trend(candles, strength=1)

    assert trend.direction == TrendDirection.SIDEWAYS
    assert trend.confidence == pytest.approx(2 / 3)


def test_analyze_trend_returns_unknown_without_enough_swings() -> None:
    candles = [
        make_candle(0, high=10, low=8),
        make_candle(1, high=11, low=9),
        make_candle(2, high=12, low=10),
    ]

    trend = analyze_trend(candles, strength=1)

    assert trend.direction == TrendDirection.UNKNOWN
    assert trend.confidence == 0
    assert trend.latest_swing_high is None
    assert trend.latest_swing_low is None


def test_find_swing_helpers_filter_by_type() -> None:
    candles = [
        make_candle(0, high=10, low=8),
        make_candle(1, high=12, low=7),
        make_candle(2, high=11, low=9),
    ]

    assert [point.point_type for point in find_swing_highs(candles, strength=1)] == [
        SwingPointType.HIGH
    ]
    assert [point.point_type for point in find_swing_lows(candles, strength=1)] == [
        SwingPointType.LOW
    ]


def test_analyze_trend_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="strength"):
        analyze_trend([], strength=0)

    with pytest.raises(ValueError, match="min_swing_pairs"):
        analyze_trend([], min_swing_pairs=0)

    with pytest.raises(ValueError, match="min_trend_confidence"):
        analyze_trend([], min_trend_confidence=2)
