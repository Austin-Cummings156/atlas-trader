"""Tests for candle analysis helpers."""

from datetime import datetime

import pytest

import atlas_trader.analysis as analysis_api
from atlas_trader.analysis.candles import (
    CandleClosePosition,
    CandleDirection,
    CandleRangeContext,
    CandleStrength,
    CandleType,
    analyze_candle,
    analyze_candle_contexts,
    analyze_candles,
    closes_above_previous_high,
    closes_below_previous_low,
    has_higher_high_than_previous,
    has_higher_low_than_previous,
    has_lower_high_than_previous,
    has_lower_low_than_previous,
    is_inside_bar,
    is_outside_bar,
)
from atlas_trader.data.models import Candle


def test_candle_api_is_exposed_from_analysis_package() -> None:
    assert analysis_api.CandleMetrics is not None
    assert analysis_api.analyze_candle is analyze_candle


def make_candle(
    *,
    open: float,
    high: float,
    low: float,
    close: float,
    volume: float = 1000,
) -> Candle:
    return Candle(
        symbol="BTC-USD",
        timestamp=datetime(2026, 1, 1),
        open=open,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def test_analyze_strong_bullish_candle() -> None:
    candle = make_candle(open=100, high=112, low=99, close=110)

    metrics = analyze_candle(candle)

    assert metrics.direction == CandleDirection.BULLISH
    assert metrics.strength == CandleStrength.STRONG
    assert metrics.candle_type == CandleType.STRONG_BULLISH
    assert metrics.body_size == 10
    assert metrics.full_range == 13
    assert metrics.close_position_ratio == pytest.approx(11 / 13)
    assert metrics.close_position == CandleClosePosition.NEAR_HIGH


def test_analyze_strong_bearish_candle() -> None:
    candle = make_candle(open=110, high=111, low=98, close=100)

    metrics = analyze_candle(candle)

    assert metrics.direction == CandleDirection.BEARISH
    assert metrics.strength == CandleStrength.STRONG
    assert metrics.candle_type == CandleType.STRONG_BEARISH


def test_analyze_indecision_candle() -> None:
    candle = make_candle(open=100, high=110, low=90, close=101)

    metrics = analyze_candle(candle)

    assert metrics.direction == CandleDirection.BULLISH
    assert metrics.strength == CandleStrength.INDECISION
    assert metrics.candle_type == CandleType.INDECISION


def test_analyze_long_upper_wick_candle() -> None:
    candle = make_candle(open=100, high=120, low=98, close=105)

    metrics = analyze_candle(candle)

    assert metrics.candle_type == CandleType.LONG_UPPER_WICK
    assert metrics.upper_wick_to_range_ratio >= 0.5


def test_analyze_long_lower_wick_candle() -> None:
    candle = make_candle(open=115, high=116, low=90, close=110)

    metrics = analyze_candle(candle)

    assert metrics.candle_type == CandleType.LONG_LOWER_WICK
    assert metrics.lower_wick_to_range_ratio >= 0.5


def test_analyze_zero_range_candle_as_indecision() -> None:
    candle = make_candle(open=100, high=100, low=100, close=100)

    metrics = analyze_candle(candle)

    assert metrics.direction == CandleDirection.NEUTRAL
    assert metrics.strength == CandleStrength.INDECISION
    assert metrics.candle_type == CandleType.INDECISION
    assert metrics.full_range == 0
    assert metrics.close_position_ratio == 0
    assert metrics.close_position == CandleClosePosition.MID_RANGE


@pytest.mark.parametrize(
    ("body_to_range_ratio", "expected_strength"),
    [
        (0.1, CandleStrength.INDECISION),
        (0.4, CandleStrength.MODERATE),
        (0.7, CandleStrength.STRONG),
    ],
)
def test_analyze_strength_thresholds(
    body_to_range_ratio: float,
    expected_strength: CandleStrength,
) -> None:
    candle = make_candle(open=100, high=200, low=100, close=100 + body_to_range_ratio * 100)

    metrics = analyze_candle(candle)

    assert metrics.body_to_range_ratio == pytest.approx(body_to_range_ratio)
    assert metrics.strength == expected_strength


def test_analyze_standard_moderate_candle() -> None:
    candle = make_candle(open=100, high=160, low=80, close=140)

    metrics = analyze_candle(candle)

    assert metrics.direction == CandleDirection.BULLISH
    assert metrics.strength == CandleStrength.MODERATE
    assert metrics.candle_type == CandleType.STANDARD


@pytest.mark.parametrize(
    ("close", "expected_position"),
    [
        (125, CandleClosePosition.NEAR_LOW),
        (150, CandleClosePosition.MID_RANGE),
        (175, CandleClosePosition.NEAR_HIGH),
    ],
)
def test_analyze_close_position_thresholds(
    close: float,
    expected_position: CandleClosePosition,
) -> None:
    candle = make_candle(open=150, high=200, low=100, close=close)

    metrics = analyze_candle(candle)

    assert metrics.close_position == expected_position


def test_analyze_candles_returns_metrics_for_each_candle() -> None:
    candles = [
        make_candle(open=100, high=110, low=95, close=108),
        make_candle(open=108, high=115, low=105, close=112),
    ]

    metrics = analyze_candles(candles)

    assert len(metrics) == 2
    assert metrics[0].direction == CandleDirection.BULLISH
    assert metrics[1].direction == CandleDirection.BULLISH


def test_candle_comparison_helpers() -> None:
    previous = make_candle(open=100, high=110, low=90, close=105)
    current = make_candle(open=106, high=115, low=95, close=112)

    assert has_higher_high_than_previous(current, previous)
    assert has_higher_low_than_previous(current, previous)
    assert not has_lower_low_than_previous(current, previous)
    assert not has_lower_high_than_previous(current, previous)
    assert closes_above_previous_high(current, previous)
    assert not closes_below_previous_low(current, previous)
    assert not is_inside_bar(current, previous)
    assert not is_outside_bar(current, previous)


def test_candle_comparison_helpers_handle_missing_previous_candle() -> None:
    candle = make_candle(open=100, high=110, low=90, close=105)

    assert not has_higher_high_than_previous(candle, None)
    assert not has_lower_low_than_previous(candle, None)
    assert not has_higher_low_than_previous(candle, None)
    assert not has_lower_high_than_previous(candle, None)
    assert not closes_above_previous_high(candle, None)
    assert not closes_below_previous_low(candle, None)
    assert not is_inside_bar(candle, None)
    assert not is_outside_bar(candle, None)


def test_inside_and_outside_bar_detection() -> None:
    previous = make_candle(open=100, high=120, low=80, close=110)
    inside = make_candle(open=105, high=115, low=90, close=100)
    outside = make_candle(open=105, high=125, low=75, close=120)

    assert is_inside_bar(inside, previous)
    assert not is_outside_bar(inside, previous)
    assert is_outside_bar(outside, previous)
    assert not is_inside_bar(outside, previous)


def test_analyze_candle_contexts_uses_prior_candles_for_range_context() -> None:
    candles = [
        make_candle(open=100, high=110, low=100, close=105),
        make_candle(open=105, high=115, low=105, close=110),
        make_candle(open=110, high=140, low=110, close=135),
        make_candle(open=136, high=140, low=135, close=138),
    ]

    contexts = analyze_candle_contexts(candles, average_range_period=2)

    assert contexts[0].previous_candle is None
    assert contexts[0].range_context == CandleRangeContext.UNKNOWN
    assert contexts[1].average_range == 10
    assert contexts[1].range_vs_average_ratio == pytest.approx(1)
    assert contexts[1].range_context == CandleRangeContext.AVERAGE
    assert contexts[2].average_range == 10
    assert contexts[2].range_vs_average_ratio == pytest.approx(3)
    assert contexts[2].range_context == CandleRangeContext.WIDE
    assert contexts[3].average_range == 20
    assert contexts[3].range_vs_average_ratio == pytest.approx(0.25)
    assert contexts[3].range_context == CandleRangeContext.NARROW


def test_analyze_candle_contexts_adds_previous_candle_flags() -> None:
    candles = [
        make_candle(open=100, high=110, low=90, close=105),
        make_candle(open=106, high=112, low=95, close=111),
    ]

    contexts = analyze_candle_contexts(candles)

    assert contexts[1].previous_candle == candles[0]
    assert contexts[1].has_higher_high_than_previous
    assert contexts[1].has_higher_low_than_previous
    assert contexts[1].closes_above_previous_high


def test_analyze_candle_contexts_rejects_invalid_average_period() -> None:
    with pytest.raises(ValueError, match="average_range_period"):
        analyze_candle_contexts([], average_range_period=0)


def test_candle_rejects_invalid_high_low_range() -> None:
    with pytest.raises(ValueError, match="high cannot be lower"):
        Candle(
            symbol="BTC-USD",
            timestamp=datetime(2026, 1, 1),
            open=100,
            high=90,
            low=110,
            close=105,
            volume=1000,
        )


def test_candle_rejects_negative_volume() -> None:
    with pytest.raises(ValueError, match="volume cannot be negative"):
        Candle(
            symbol="BTC-USD",
            timestamp=datetime(2026, 1, 1),
            open=100,
            high=110,
            low=90,
            close=105,
            volume=-1,
        )


@pytest.mark.parametrize("bad_price", [0, -1])
def test_candle_rejects_non_positive_prices(bad_price: float) -> None:
    with pytest.raises(ValueError, match="prices must be greater than zero"):
        Candle(
            symbol="BTC-USD",
            timestamp=datetime(2026, 1, 1),
            open=bad_price,
            high=110,
            low=90,
            close=105,
            volume=1000,
        )


@pytest.mark.parametrize("bad_price", [float("nan"), float("inf"), float("-inf")])
def test_candle_rejects_non_finite_prices(bad_price: float) -> None:
    with pytest.raises(ValueError, match="prices must be finite"):
        Candle(
            symbol="BTC-USD",
            timestamp=datetime(2026, 1, 1),
            open=bad_price,
            high=110,
            low=90,
            close=105,
            volume=1000,
        )


@pytest.mark.parametrize("bad_volume", [float("nan"), float("inf"), float("-inf")])
def test_candle_rejects_non_finite_volume(bad_volume: float) -> None:
    with pytest.raises(ValueError, match="volume must be a finite"):
        Candle(
            symbol="BTC-USD",
            timestamp=datetime(2026, 1, 1),
            open=100,
            high=110,
            low=90,
            close=105,
            volume=bad_volume,
        )
