"""Tests for volume analysis helpers."""

from datetime import datetime, timedelta

import pytest

import atlas_trader.analysis as analysis_api
from atlas_trader.analysis.ranges import BreakoutDirection
from atlas_trader.analysis.volume import (
    BreakoutVolumeContext,
    RelativeVolumeLevel,
    VolumeAnalysisSettings,
    VolumeTrend,
    analyze_volume,
    analyze_volume_contexts,
    relative_volume,
    volume_average,
    volume_trend,
)
from atlas_trader.data.models import Candle


def make_candle(index: int, volume: float) -> Candle:
    return Candle(
        symbol="BTC-USD",
        timestamp=datetime(2026, 1, 1) + timedelta(days=index),
        open=100,
        high=105,
        low=95,
        close=102,
        volume=volume,
    )


def test_volume_api_is_exposed_from_analysis_package() -> None:
    assert analysis_api.VolumeAnalysisSettings is VolumeAnalysisSettings
    assert analysis_api.analyze_volume is analyze_volume
    assert analysis_api.VolumeTrend is VolumeTrend


def test_volume_average_and_relative_volume_helpers() -> None:
    candles = [make_candle(0, 100), make_candle(1, 200), make_candle(2, 300)]

    assert volume_average([100, 200, 300], period=2) == pytest.approx(250)
    assert volume_average(candles, period=3) == pytest.approx(200)
    assert volume_average(candles, period=4) is None
    assert relative_volume(300, 200) == pytest.approx(1.5)
    assert relative_volume(300, None) is None
    assert relative_volume(300, 0) is None


def test_analyze_volume_classifies_latest_relative_volume_and_trend() -> None:
    candles = [
        make_candle(0, 100),
        make_candle(1, 120),
        make_candle(2, 140),
        make_candle(3, 300),
    ]
    settings = VolumeAnalysisSettings(default_average_period=3, trend_period=3)

    context = analyze_volume(candles, settings=settings)

    assert context.average_volume == pytest.approx(120)
    assert context.relative_volume == pytest.approx(2.5)
    assert context.relative_volume_level == RelativeVolumeLevel.HIGH
    assert context.volume_trend == VolumeTrend.RISING
    assert context.breakout_context == BreakoutVolumeContext.ABSENT


def test_analyze_volume_contexts_uses_prior_candles_for_average() -> None:
    candles = [
        make_candle(0, 100),
        make_candle(1, 200),
        make_candle(2, 100),
        make_candle(3, 50),
    ]

    contexts = analyze_volume_contexts(candles, average_period=2)

    assert contexts[0].average_volume is None
    assert contexts[1].average_volume is None
    assert contexts[2].average_volume == pytest.approx(150)
    assert contexts[2].relative_volume == pytest.approx(2 / 3)
    assert contexts[2].relative_volume_level == RelativeVolumeLevel.LOW
    assert contexts[3].average_volume == pytest.approx(150)


def test_volume_trend_classifies_rising_falling_flat_and_mixed() -> None:
    settings = VolumeAnalysisSettings(trend_period=3, flat_volume_tolerance_ratio=0.05)

    assert volume_trend([100, 120, 150], settings=settings) == VolumeTrend.RISING
    assert volume_trend([150, 120, 100], settings=settings) == VolumeTrend.FALLING
    assert volume_trend([100, 103, 101], settings=settings) == VolumeTrend.FLAT
    assert volume_trend([100, 130, 120], settings=settings) == VolumeTrend.MIXED
    assert volume_trend([100, 120], settings=settings) == VolumeTrend.UNKNOWN


def test_breakout_volume_context_confirms_high_relative_volume_breakout() -> None:
    candles = [
        make_candle(0, 100),
        make_candle(1, 100),
        make_candle(2, 100),
        make_candle(3, 200),
    ]
    settings = VolumeAnalysisSettings(default_average_period=3, breakout_relative_volume_ratio=1.5)

    confirmed = analyze_volume(
        candles,
        breakout_direction=BreakoutDirection.UP,
        settings=settings,
    )
    weak = analyze_volume(
        [*candles[:-1], make_candle(3, 120)],
        breakout_direction=BreakoutDirection.DOWN,
        settings=settings,
    )

    assert confirmed.breakout_context == BreakoutVolumeContext.CONFIRMED
    assert weak.breakout_context == BreakoutVolumeContext.WEAK


def test_analyze_volume_contexts_accepts_per_candle_breakout_directions() -> None:
    candles = [make_candle(0, 100), make_candle(1, 100), make_candle(2, 200)]

    contexts = analyze_volume_contexts(
        candles,
        average_period=2,
        breakout_directions=[
            BreakoutDirection.NONE,
            BreakoutDirection.NONE,
            BreakoutDirection.UP,
        ],
    )

    assert contexts[2].breakout_context == BreakoutVolumeContext.CONFIRMED


def test_volume_analysis_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="candles"):
        analyze_volume([])

    with pytest.raises(ValueError, match="average_period"):
        analyze_volume_contexts([], average_period=0)

    with pytest.raises(ValueError, match="breakout_directions"):
        analyze_volume_contexts([make_candle(0, 100)], breakout_directions=[])

    with pytest.raises(ValueError, match="trend_period"):
        VolumeAnalysisSettings(trend_period=1)
