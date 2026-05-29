"""Tests for support, resistance, and moving-average helpers."""

from datetime import datetime, timedelta

import pytest

import atlas_trader.analysis as analysis_api
from atlas_trader.analysis.support_resistance import (
    LevelPosition,
    LevelType,
    SupportResistanceSettings,
    analyze_support_resistance,
    candle_close_moving_average,
    moving_average_context,
    simple_moving_average,
)
from atlas_trader.data.models import Candle


def make_candle(
    index: int,
    *,
    high: float,
    low: float,
    close: float,
    open: float | None = None,
) -> Candle:
    open_price = close if open is None else open
    return Candle(
        symbol="BTC-USD",
        timestamp=datetime(2026, 1, 1) + timedelta(days=index),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1000,
    )


def test_support_resistance_api_is_exposed_from_analysis_package() -> None:
    assert analysis_api.SupportResistanceSettings is SupportResistanceSettings
    assert analysis_api.analyze_support_resistance is analyze_support_resistance
    assert analysis_api.LevelType is LevelType


def test_detects_support_and_resistance_from_clustered_swing_points() -> None:
    candles = [
        make_candle(0, high=104, low=101, close=102),
        make_candle(1, high=111, low=98, close=104),
        make_candle(2, high=106, low=102, close=105),
        make_candle(3, high=112, low=99, close=106),
        make_candle(4, high=107, low=103, close=104),
        make_candle(5, high=111.5, low=98.5, close=105),
        make_candle(6, high=108, low=104, close=105.5),
    ]
    settings = SupportResistanceSettings(level_tolerance_ratio=0.02)

    analysis = analyze_support_resistance(candles, strength=1, settings=settings)

    assert len(analysis.support_levels) == 1
    assert len(analysis.resistance_levels) == 1
    assert analysis.nearest_support == analysis.support_levels[0]
    assert analysis.nearest_resistance == analysis.resistance_levels[0]
    assert analysis.nearest_support.level_type == LevelType.SUPPORT
    assert analysis.nearest_support.touches == 3
    assert analysis.nearest_support.price == pytest.approx((98 + 99 + 98.5) / 3)
    assert analysis.nearest_support.position == LevelPosition.ABOVE
    assert analysis.nearest_resistance.level_type == LevelType.RESISTANCE
    assert analysis.nearest_resistance.touches == 3
    assert analysis.nearest_resistance.position == LevelPosition.BELOW
    assert analysis.nearest_resistance.confidence > 0


def test_support_resistance_uses_lookback_window() -> None:
    candles = [
        make_candle(0, high=120, low=80, close=100),
        make_candle(1, high=121, low=81, close=100),
        make_candle(2, high=104, low=101, close=102),
        make_candle(3, high=111, low=98, close=104),
        make_candle(4, high=106, low=102, close=105),
        make_candle(5, high=112, low=99, close=106),
        make_candle(6, high=107, low=103, close=104),
        make_candle(7, high=111.5, low=98.5, close=105),
        make_candle(8, high=108, low=104, close=105.5),
    ]

    analysis = analyze_support_resistance(candles, lookback=7, strength=1)

    assert analysis.nearest_support is not None
    assert analysis.nearest_support.price > 90


def test_moving_average_helpers_return_latest_simple_average_and_context() -> None:
    candles = [
        make_candle(0, high=101, low=99, close=100),
        make_candle(1, high=102, low=100, close=101),
        make_candle(2, high=103, low=101, close=102),
        make_candle(3, high=104, low=102, close=103),
    ]

    assert simple_moving_average([1, 2, 3, 4], period=3) == pytest.approx(3)
    assert candle_close_moving_average(candles, period=3) == pytest.approx(102)

    context = moving_average_context(candles, period=3)

    assert context.value == pytest.approx(102)
    assert context.distance_from_close == pytest.approx(1)
    assert context.position == LevelPosition.NEAR


def test_moving_average_returns_unknown_without_enough_values() -> None:
    candles = [make_candle(0, high=101, low=99, close=100)]

    assert simple_moving_average([100], period=2) is None

    context = moving_average_context(candles, period=2)

    assert context.value is None
    assert context.position == LevelPosition.UNKNOWN


def test_support_resistance_empty_input_keeps_requested_moving_average_context() -> None:
    analysis = analyze_support_resistance([])

    assert analysis.support_levels == []
    assert analysis.resistance_levels == []
    assert analysis.moving_average is not None
    assert analysis.moving_average.position == LevelPosition.UNKNOWN


def test_support_resistance_does_not_validate_unused_moving_average_period() -> None:
    analysis = analyze_support_resistance(
        [],
        include_moving_average=False,
        moving_average_period=0,
    )

    assert analysis.moving_average is None


def test_support_resistance_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="lookback"):
        analyze_support_resistance([], lookback=1)

    with pytest.raises(ValueError, match="strength"):
        analyze_support_resistance([], strength=0)

    with pytest.raises(ValueError, match="period"):
        simple_moving_average([1, 2], period=0)

    with pytest.raises(ValueError, match="level_tolerance_ratio"):
        SupportResistanceSettings(level_tolerance_ratio=-0.1)
