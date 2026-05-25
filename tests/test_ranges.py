"""Tests for sideways market analysis helpers."""

from datetime import datetime, timedelta

import pytest

import atlas_trader.analysis as analysis_api
from atlas_trader.analysis.ranges import (
    BreakoutDirection,
    SidewaysMarketType,
    analyze_sideways_market,
)
from atlas_trader.data.models import Candle


def make_candle(
    index: int,
    *,
    open: float,
    high: float,
    low: float,
    close: float,
) -> Candle:
    return Candle(
        symbol="BTC-USD",
        timestamp=datetime(2026, 1, 1) + timedelta(days=index),
        open=open,
        high=high,
        low=low,
        close=close,
        volume=1000,
    )


def test_sideways_api_is_exposed_from_analysis_package() -> None:
    assert analysis_api.SidewaysMarketAnalysis is not None
    assert analysis_api.analyze_sideways_market is analyze_sideways_market


def test_detects_trading_range_with_repeated_support_and_resistance_touches() -> None:
    candles = [
        make_candle(0, open=101, high=110, low=99, close=108),
        make_candle(1, open=108, high=111, low=101, close=103),
        make_candle(2, open=103, high=106, low=98, close=100),
        make_candle(3, open=100, high=109, low=99, close=107),
        make_candle(4, open=107, high=112, low=102, close=104),
        make_candle(5, open=104, high=107, low=98, close=101),
    ]

    analysis = analyze_sideways_market(candles)

    assert analysis.market_type == SidewaysMarketType.TRADING_RANGE
    assert analysis.is_sideways
    assert analysis.upper_bound == 112
    assert analysis.lower_bound == 98
    assert analysis.support_touches >= 2
    assert analysis.resistance_touches >= 2
    assert analysis.breakout_direction == BreakoutDirection.NONE
    assert analysis.confidence > 0


def test_detects_congestion_as_tight_overlapping_sideways_band() -> None:
    candles = [
        make_candle(0, open=100.0, high=101.0, low=99.8, close=100.4),
        make_candle(1, open=100.4, high=101.2, low=100.0, close=100.7),
        make_candle(2, open=100.7, high=101.4, low=100.2, close=100.5),
        make_candle(3, open=100.5, high=101.1, low=99.9, close=100.2),
        make_candle(4, open=100.2, high=101.3, low=100.1, close=100.6),
    ]

    analysis = analyze_sideways_market(candles, min_boundary_touches=4)

    assert analysis.market_type == SidewaysMarketType.CONGESTION
    assert analysis.is_sideways
    assert analysis.height_pct < 0.04
    assert analysis.average_candle_range_pct < 0.02


def test_detects_consolidation_as_bounded_pause_without_range_touches() -> None:
    candles = [
        make_candle(0, open=100, high=104, low=99, close=102),
        make_candle(1, open=102, high=105, low=101, close=103),
        make_candle(2, open=103, high=106, low=102, close=104),
        make_candle(3, open=104, high=105, low=100, close=101),
        make_candle(4, open=101, high=104, low=100, close=102),
    ]

    analysis = analyze_sideways_market(candles, min_boundary_touches=4)

    assert analysis.market_type == SidewaysMarketType.CONSOLIDATION
    assert analysis.is_sideways
    assert analysis.height_pct <= 0.10
    assert analysis.close_drift_ratio <= 0.60


def test_detects_directional_market_as_not_sideways() -> None:
    candles = [
        make_candle(0, open=100, high=104, low=99, close=103),
        make_candle(1, open=103, high=108, low=102, close=107),
        make_candle(2, open=107, high=113, low=106, close=112),
        make_candle(3, open=112, high=119, low=111, close=118),
        make_candle(4, open=118, high=126, low=117, close=125),
    ]

    analysis = analyze_sideways_market(candles)

    assert analysis.market_type == SidewaysMarketType.NOT_SIDEWAYS
    assert not analysis.is_sideways
    assert analysis.confidence == 0


def test_analyze_sideways_market_uses_lookback_window() -> None:
    candles = [
        make_candle(0, open=80, high=90, low=78, close=89),
        make_candle(1, open=89, high=100, low=88, close=99),
        make_candle(2, open=100, high=104, low=99, close=102),
        make_candle(3, open=102, high=105, low=101, close=103),
        make_candle(4, open=103, high=106, low=102, close=104),
        make_candle(5, open=104, high=105, low=100, close=101),
        make_candle(6, open=101, high=104, low=100, close=102),
    ]

    analysis = analyze_sideways_market(candles, lookback=5, min_boundary_touches=4)

    assert analysis.market_type == SidewaysMarketType.CONSOLIDATION
    assert analysis.lower_bound == 99
    assert analysis.upper_bound == 106


def test_analyze_sideways_market_returns_unknown_without_enough_candles() -> None:
    analysis = analyze_sideways_market([])

    assert analysis.market_type == SidewaysMarketType.UNKNOWN
    assert analysis.upper_bound is None
    assert analysis.confidence == 0


def test_analyze_sideways_market_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="lookback"):
        analyze_sideways_market([], lookback=1)

    with pytest.raises(ValueError, match="boundary_tolerance_ratio"):
        analyze_sideways_market([], boundary_tolerance_ratio=-0.1)

    with pytest.raises(ValueError, match="min_boundary_touches"):
        analyze_sideways_market([], min_boundary_touches=0)

    with pytest.raises(ValueError, match="height thresholds"):
        analyze_sideways_market(
            [],
            max_sideways_height_pct=0.05,
            max_consolidation_height_pct=0.10,
        )
