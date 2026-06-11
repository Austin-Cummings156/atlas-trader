"""Tests for report-only moving-average context helpers."""

from datetime import datetime, timedelta

import pytest

import atlas_trader.analysis as analysis_api
from atlas_trader.analysis.moving_averages import (
    MovingAveragePosition,
    analyze_moving_average_context,
    candle_close_exponential_moving_average,
    exponential_moving_average,
)
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


def flat_candles(count: int, close: float = 100) -> list[Candle]:
    return [make_candle(index, close) for index in range(count)]


def test_moving_average_api_is_exposed_from_analysis_package() -> None:
    assert analysis_api.analyze_moving_average_context is analyze_moving_average_context
    assert analysis_api.MovingAveragePosition is MovingAveragePosition


def test_exponential_moving_average_helpers() -> None:
    assert exponential_moving_average([100, 100, 100], period=3) == 100
    assert exponential_moving_average([100, 100], period=3) is None
    assert candle_close_exponential_moving_average(flat_candles(20), period=20) == 100

    with pytest.raises(ValueError, match="period"):
        exponential_moving_average([], period=0)


def test_moving_average_context_reports_unknown_without_enough_candles() -> None:
    context = analyze_moving_average_context(flat_candles(10))

    assert context.ema_20.value is None
    assert context.ema_20.position == MovingAveragePosition.UNKNOWN
    assert context.ema_50.value is None
    assert context.ema_200.value is None
    assert context.nearest_ma_support is None
    assert context.nearest_ma_resistance is None


def test_moving_average_context_reports_near_ema50() -> None:
    candles = [*flat_candles(199), make_candle(199, 101)]

    context = analyze_moving_average_context(candles)

    assert context.ema_50.position == MovingAveragePosition.NEAR
    assert context.ema_200.position == MovingAveragePosition.NEAR
    assert context.nearest_ma_support is not None
    assert context.nearest_ma_support.name == "EMA20"


def test_moving_average_context_reports_above_ema50_and_ema200() -> None:
    candles = [*flat_candles(199), make_candle(199, 110)]

    context = analyze_moving_average_context(candles)

    assert context.ema_50.position == MovingAveragePosition.ABOVE
    assert context.ema_200.position == MovingAveragePosition.ABOVE
    assert context.nearest_ma_support is not None
    assert context.nearest_ma_support.name == "EMA20"
    assert context.nearest_ma_resistance is None
