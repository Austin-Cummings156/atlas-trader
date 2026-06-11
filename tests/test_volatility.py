"""Tests for volatility context helpers."""

from datetime import datetime, timedelta

import pytest

import atlas_trader.analysis as analysis_api
from atlas_trader.analysis.volatility import (
    VolatilityAnalysisSettings,
    VolatilityLevel,
    analyze_volatility,
    high_low_range_pct,
    true_range_values,
)
from atlas_trader.data.models import Candle


def make_candle(index: int, *, close: float = 100, range_size: float = 2) -> Candle:
    half_range = range_size / 2
    return Candle(
        symbol="TEST",
        timestamp=datetime(2026, 1, 1) + timedelta(days=index),
        open=close,
        high=close + half_range,
        low=close - half_range,
        close=close,
        volume=1000,
    )


def regime_candles(*, baseline_range: float, recent_range: float) -> list[Candle]:
    baseline = [make_candle(index, range_size=baseline_range) for index in range(60)]
    recent = [make_candle(index + 60, range_size=recent_range) for index in range(14)]
    return [*baseline, *recent]


def test_volatility_api_is_exposed_from_analysis_package() -> None:
    assert analysis_api.VolatilityAnalysisSettings is VolatilityAnalysisSettings
    assert analysis_api.VolatilityLevel is VolatilityLevel
    assert analysis_api.analyze_volatility is analyze_volatility


def test_true_range_and_high_low_range_percent_helpers() -> None:
    candles = [
        make_candle(0, close=100, range_size=4),
        Candle(
            symbol="TEST",
            timestamp=datetime(2026, 1, 2),
            open=105,
            high=107,
            low=104,
            close=106,
            volume=1000,
        ),
    ]

    assert true_range_values(candles) == [4, 7]
    assert high_low_range_pct(candles[0]) == pytest.approx(0.04)


def test_analyze_volatility_classifies_low_regime() -> None:
    context = analyze_volatility(regime_candles(baseline_range=2, recent_range=0.5))

    assert context.level == VolatilityLevel.LOW
    assert context.average_true_range == pytest.approx(0.5)
    assert context.average_true_range_pct == pytest.approx(0.005)
    assert context.recent_vs_baseline_atr_ratio < 0.75
    assert context.insufficient_data_reason is None


def test_analyze_volatility_classifies_normal_regime() -> None:
    context = analyze_volatility(regime_candles(baseline_range=2, recent_range=2))

    assert context.level == VolatilityLevel.NORMAL
    assert context.average_true_range_pct == pytest.approx(0.02)
    assert context.baseline_average_true_range_pct == pytest.approx(0.02)
    assert context.recent_vs_baseline_atr_ratio == pytest.approx(1)


def test_analyze_volatility_classifies_high_regime() -> None:
    context = analyze_volatility(regime_candles(baseline_range=2, recent_range=5))

    assert context.level == VolatilityLevel.HIGH
    assert context.average_true_range_pct == pytest.approx(0.05)
    assert context.recent_vs_baseline_atr_ratio > 1.5


def test_analyze_volatility_handles_insufficient_data() -> None:
    context = analyze_volatility([make_candle(index) for index in range(5)])

    assert context.level == VolatilityLevel.UNKNOWN
    assert context.average_true_range is None
    assert context.recent_vs_baseline_atr_ratio is None
    assert context.insufficient_data_reason == (
        "requires at least 14 candles for recent volatility"
    )


def test_volatility_settings_reject_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="recent_period"):
        VolatilityAnalysisSettings(recent_period=0)

    with pytest.raises(ValueError, match="min_baseline_period"):
        VolatilityAnalysisSettings(baseline_period=10, min_baseline_period=20)

    with pytest.raises(ValueError, match="relative volatility thresholds"):
        VolatilityAnalysisSettings(low_relative_volatility_ratio=2)
