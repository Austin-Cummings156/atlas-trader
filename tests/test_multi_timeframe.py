"""Tests for multi-timeframe analysis helpers."""

from datetime import datetime, timedelta

import pytest

import atlas_trader.analysis as analysis_api
from atlas_trader.analysis.multi_timeframe import (
    MultiTimeframeAlignment,
    MultiTimeframeSettings,
    TimeframeBias,
    TimeframeRole,
    analyze_multi_timeframe,
    analyze_timeframe,
)
from atlas_trader.analysis.trends import TrendDirection
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
        volume=1000 + index * 10,
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
    ]


def downtrend_candles() -> list[Candle]:
    return [
        make_candle(0, high=20, low=17),
        make_candle(1, high=24, low=18),
        make_candle(2, high=21, low=14),
        make_candle(3, high=22, low=15),
        make_candle(4, high=19, low=12),
        make_candle(5, high=20, low=13),
        make_candle(6, high=17, low=10),
    ]


def sideways_candles() -> list[Candle]:
    return [
        make_candle(0, high=110, low=99, close=108),
        make_candle(1, high=111, low=101, close=103),
        make_candle(2, high=106, low=98, close=100),
        make_candle(3, high=109, low=99, close=107),
        make_candle(4, high=112, low=102, close=104),
        make_candle(5, high=107, low=98, close=101),
    ]


def test_multi_timeframe_api_is_exposed_from_analysis_package() -> None:
    assert analysis_api.MultiTimeframeSettings is MultiTimeframeSettings
    assert analysis_api.MultiTimeframeAlignment is MultiTimeframeAlignment
    assert analysis_api.analyze_multi_timeframe is analyze_multi_timeframe


def test_analyze_timeframe_composes_existing_market_readers() -> None:
    settings = MultiTimeframeSettings(trend_strength=1)

    analysis = analyze_timeframe(
        "1d",
        uptrend_candles(),
        role=TimeframeRole.PRIMARY,
        settings=settings,
    )

    assert analysis.timeframe == "1d"
    assert analysis.role == TimeframeRole.PRIMARY
    assert analysis.latest_candle == analysis.candles[-1]
    assert analysis.trend.direction == TrendDirection.UPTREND
    assert analysis.bias == TimeframeBias.BULLISH
    assert analysis.confidence > 0
    assert analysis.support_resistance is not None
    assert analysis.volume is not None


def test_analyze_multi_timeframe_detects_strong_bullish_alignment() -> None:
    settings = MultiTimeframeSettings(trend_strength=1)

    analysis = analyze_multi_timeframe(
        {
            "4h": uptrend_candles(),
            "1d": uptrend_candles(),
            "1y": uptrend_candles(),
        },
        settings=settings,
    )

    assert analysis.directional_bias == TimeframeBias.BULLISH
    assert analysis.alignment == MultiTimeframeAlignment.STRONG_BULLISH
    assert analysis.confidence > 0
    assert analysis.conflicts == []
    assert analysis.recent is analysis.timeframes["4h"]
    assert analysis.primary is analysis.timeframes["1d"]
    assert analysis.long_term is analysis.timeframes["1y"]


def test_analyze_multi_timeframe_reports_directional_conflicts() -> None:
    settings = MultiTimeframeSettings(trend_strength=1)

    analysis = analyze_multi_timeframe(
        {
            "4h": downtrend_candles(),
            "1d": uptrend_candles(),
        },
        settings=settings,
    )

    assert analysis.alignment == MultiTimeframeAlignment.CONFLICTED
    assert analysis.has_conflicts
    assert analysis.conflicts == ["4h is bearish; 1d is bullish"]


def test_analyze_multi_timeframe_can_classify_sideways_alignment() -> None:
    settings = MultiTimeframeSettings(trend_strength=1)

    analysis = analyze_multi_timeframe(
        {
            "4h": sideways_candles(),
            "1d": sideways_candles(),
        },
        settings=settings,
    )

    assert analysis.directional_bias == TimeframeBias.SIDEWAYS
    assert analysis.alignment == MultiTimeframeAlignment.SIDEWAYS
    assert not analysis.has_conflicts


def test_multi_timeframe_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="timeframe_candles"):
        analyze_multi_timeframe({})

    with pytest.raises(ValueError, match="timeframe"):
        analyze_timeframe("", [])

    with pytest.raises(ValueError, match="trend_strength"):
        MultiTimeframeSettings(trend_strength=0)

    with pytest.raises(ValueError, match="min_aligned_timeframes"):
        MultiTimeframeSettings(min_aligned_timeframes=0)
