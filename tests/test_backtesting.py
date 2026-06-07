"""Tests for historical market-reading validation helpers."""

from datetime import datetime, timedelta

import pytest

import atlas_trader.backtesting as backtesting_api
from atlas_trader.analysis.ranges import BreakoutDirection
from atlas_trader.analysis.trends import TrendDirection
from atlas_trader.backtesting import (
    HistoricalAuditReason,
    HistoricalReadBias,
    HistoricalReadSettings,
    analyze_historical_market,
)
from atlas_trader.data.models import Candle


def make_candle(
    index: int,
    *,
    high: float,
    low: float,
    close: float | None = None,
    volume: float | None = None,
) -> Candle:
    close_price = close if close is not None else (high + low) / 2
    return Candle(
        symbol="TEST",
        timestamp=datetime(2026, 1, 1) + timedelta(days=index),
        open=close_price,
        high=high,
        low=low,
        close=close_price,
        volume=volume if volume is not None else 1000 + index * 100,
    )


def uptrend_candles() -> list[Candle]:
    return [
        make_candle(0, high=10, low=7),
        make_candle(1, high=14, low=10),
        make_candle(2, high=11, low=9),
        make_candle(3, high=16, low=12),
        make_candle(4, high=13, low=10.5),
        make_candle(5, high=18, low=13),
        make_candle(6, high=15, low=13),
        make_candle(7, high=20, low=15),
        make_candle(8, high=17, low=14.5),
    ]


def range_then_breakout_candles() -> list[Candle]:
    return [
        make_candle(0, high=110, low=99, close=108),
        make_candle(1, high=111, low=101, close=103),
        make_candle(2, high=106, low=98, close=100),
        make_candle(3, high=109, low=99, close=107),
        make_candle(4, high=112, low=102, close=104),
        make_candle(5, high=107, low=98, close=101),
        make_candle(6, high=120, low=109, close=119, volume=3000),
    ]


def test_historical_read_api_is_exposed_from_backtesting_package() -> None:
    assert backtesting_api.HistoricalReadSettings is HistoricalReadSettings
    assert backtesting_api.analyze_historical_market is analyze_historical_market


def test_analyze_historical_market_builds_rolling_snapshots() -> None:
    settings = HistoricalReadSettings(
        lookback=9,
        min_window=7,
        step=1,
        trend_strength=1,
    )

    report = analyze_historical_market(uptrend_candles(), settings=settings)

    assert report.symbol == "TEST"
    assert report.snapshot_count == 3
    assert report.latest_snapshot is report.snapshots[-1]
    assert report.latest_snapshot.index == 8
    assert report.latest_snapshot.window_size == 9
    assert report.latest_snapshot.trend.direction == TrendDirection.UPTREND
    assert report.latest_snapshot.bias == HistoricalReadBias.BULLISH
    assert report.trend_counts[TrendDirection.UPTREND] >= 1
    assert report.bias_counts[HistoricalReadBias.BULLISH] >= 1
    assert report.high_relative_volume_count >= 0


def test_analyze_historical_market_detects_breakout_snapshots() -> None:
    settings = HistoricalReadSettings(lookback=7, step=1, volume_average_period=3)

    report = analyze_historical_market(range_then_breakout_candles(), settings=settings)
    latest = report.latest_snapshot

    assert latest is not None
    assert latest.sideways_market.breakout_direction == BreakoutDirection.UP
    assert latest.bias == HistoricalReadBias.BULLISH
    assert report.breakout_counts[BreakoutDirection.UP] == 1


def test_historical_read_report_selects_audit_events() -> None:
    settings = HistoricalReadSettings(lookback=7, step=1, volume_average_period=3)

    report = analyze_historical_market(range_then_breakout_candles(), settings=settings)
    events = report.audit_events()

    assert events
    assert events[-1].snapshot.sideways_market.breakout_direction == BreakoutDirection.UP
    assert HistoricalAuditReason.BREAKOUT in events[-1].reasons
    assert HistoricalAuditReason.HIGH_RELATIVE_VOLUME in events[-1].reasons


def test_historical_read_settings_support_min_window_and_step() -> None:
    settings = HistoricalReadSettings(lookback=5, min_window=3, step=2, trend_strength=1)

    report = analyze_historical_market(uptrend_candles(), settings=settings)

    assert [snapshot.index for snapshot in report.snapshots] == [2, 4, 6, 8]
    assert all(snapshot.window_size <= 5 for snapshot in report.snapshots)


def test_historical_market_read_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="candles"):
        analyze_historical_market([])

    with pytest.raises(ValueError, match="lookback"):
        HistoricalReadSettings(lookback=1)

    with pytest.raises(ValueError, match="step"):
        HistoricalReadSettings(step=0)

    with pytest.raises(ValueError, match="min_window"):
        HistoricalReadSettings(lookback=5, min_window=6)
