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


def downtrend_candles() -> list[Candle]:
    return [
        make_candle(0, high=20, low=17),
        make_candle(1, high=24, low=18),
        make_candle(2, high=21, low=14),
        make_candle(3, high=22, low=15),
        make_candle(4, high=19, low=12),
        make_candle(5, high=20, low=13),
        make_candle(6, high=17, low=10),
        make_candle(7, high=18, low=11),
        make_candle(8, high=15, low=8),
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


def mixed_sideways_structure_candles() -> list[Candle]:
    return [
        make_candle(0, high=10, low=7),
        make_candle(1, high=14, low=8),
        make_candle(2, high=11, low=6),
        make_candle(3, high=13, low=9),
        make_candle(4, high=10, low=5),
        make_candle(5, high=15, low=8),
        make_candle(6, high=12, low=6),
    ]


def broad_uptrend_with_recent_pullback_candles() -> list[Candle]:
    candles: list[Candle] = []
    for index in range(220):
        base = 100 + index * 0.5
        if index % 2 == 0:
            candles.append(make_candle(index, high=base + 1, low=base - 2, close=base))
        else:
            candles.append(make_candle(index, high=base + 8, low=base + 5, close=base + 6))

    for offset, close in enumerate([214, 210, 206, 202, 198]):
        index = 215 + offset
        candles[index] = make_candle(index, high=close + 1, low=close - 1, close=close)

    return candles


def messy_directional_candles(*, direction: int) -> list[Candle]:
    candles: list[Candle] = []
    base_price = 100 if direction > 0 else 220
    pattern = [
        (10, 7),
        (14, 8),
        (11, 6),
        (13, 9),
        (10, 5),
        (15, 8),
        (12, 6),
    ]

    for cycle in range(35):
        drift = cycle * direction
        for high, low in pattern:
            index = len(candles)
            candles.append(
                make_candle(
                    index,
                    high=base_price + drift + high,
                    low=base_price + drift + low,
                )
            )

    return candles


def ko_like_range_candles(*, direction: int) -> list[Candle]:
    candles: list[Candle] = []

    candle_count = 220
    for index in range(candle_count):
        progress = index / (candle_count - 1)
        oscillation = 0.6 if index % 2 == 0 else -0.6
        close = 102 + progress * 6 + oscillation
        if direction < 0:
            close = 110 - progress * 6 + oscillation
        candles.append(
            make_candle(
                index,
                high=max(112, close + 1),
                low=min(100, close - 1),
                close=close,
            )
        )

    return candles


def steady_uptrend_candles(count: int) -> list[Candle]:
    return [
        make_candle(
            index,
            high=100 + index + 1,
            low=100 + index - 1,
            close=100 + index,
        )
        for index in range(count)
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


def test_historical_snapshot_debug_report_has_stable_fields() -> None:
    settings = HistoricalReadSettings(
        lookback=9,
        min_window=9,
        trend_strength=1,
        volume_average_period=3,
    )

    report = analyze_historical_market(uptrend_candles(), settings=settings)
    snapshot_report = report.snapshot_debug_reports(timeframe="1d")[0]

    assert tuple(snapshot_report) == (
        "symbol",
        "timeframe",
        "snapshot_index",
        "candle_timestamp",
        "candle_date",
        "window_size",
        "indicator_window_size",
        "latest_close",
        "bias",
        "trend_direction",
        "trend_confidence",
        "market_type",
        "market_confidence",
        "latest_swing_high",
        "latest_swing_low",
        "recent_swing_high",
        "recent_swing_low",
        "swing_highs",
        "swing_lows",
        "confirmed_swing_high_count",
        "confirmed_swing_low_count",
        "higher_high_count",
        "higher_low_count",
        "lower_high_count",
        "lower_low_count",
        "equal_high_count",
        "equal_low_count",
        "higher_high_ratio",
        "higher_low_ratio",
        "lower_high_ratio",
        "lower_low_ratio",
        "trend_fallback_reason",
        "insufficient_swing_structure",
        "trend_candidate",
        "trend_candidate_confidence",
        "trend_candidate_raw_score",
        "trend_candidate_conflict_count",
        "trend_candidate_effective_score",
        "trend_candidate_threshold",
        "trend_candidate_selected_score",
        "trend_candidate_blocked_reason",
        "trend_candidate_raw_reasons",
        "trend_candidate_reasons",
        "trend_candidate_conflicts",
        "messy_trend_candidate",
        "messy_trend_direction",
        "window_return_pct",
        "range_upper_bound",
        "range_lower_bound",
        "range_midpoint",
        "range_height",
        "range_height_pct",
        "close_drift",
        "close_drift_ratio",
        "support_touches",
        "resistance_touches",
        "breakout_direction",
        "nearest_support",
        "nearest_resistance",
        "nearest_support_price",
        "nearest_resistance_price",
        "distance_from_support",
        "distance_from_support_pct",
        "distance_from_resistance",
        "distance_from_resistance_pct",
        "average_volume",
        "relative_volume",
        "relative_volume_level",
        "volume_trend",
        "breakout_volume_context",
        "volatility_level",
        "average_true_range",
        "average_true_range_pct",
        "average_high_low_range_pct",
        "baseline_average_true_range_pct",
        "recent_vs_baseline_atr_ratio",
        "volatility_recent_period",
        "volatility_baseline_period",
        "volatility_insufficient_data_reason",
        "ema_20",
        "ema_50",
        "ema_200",
        "price_vs_ema_20",
        "price_vs_ema_50",
        "price_vs_ema_200",
        "nearest_ma_support",
        "nearest_ma_resistance",
        "short_term_pressure",
        "trend_condition",
        "recent_return_pct",
        "consecutive_down_closes",
        "consecutive_up_closes",
        "pullback_from_recent_high_pct",
        "bounce_from_recent_low_pct",
        "trend_health_reasons",
        "multi_timeframe_bias",
        "multi_timeframe_alignment",
        "multi_timeframe_conflicts",
        "audit_reasons",
        "unknown_reasons",
        "market_read_status",
        "market_read_summary",
        "caution_notes",
        "key_levels_summary",
        "actionability",
    )
    assert snapshot_report["symbol"] == "TEST"
    assert snapshot_report["timeframe"] == "1d"
    assert snapshot_report["trend_direction"] == "uptrend"
    assert snapshot_report["trend_candidate"] == "uptrend"
    assert snapshot_report["messy_trend_candidate"] is False
    assert snapshot_report["higher_high_count"] > 0
    assert snapshot_report["higher_low_count"] > 0
    assert snapshot_report["volatility_level"] == "unknown"
    assert snapshot_report["ema_20"] is None
    assert snapshot_report["short_term_pressure"] == "bullish"


def test_historical_report_debug_output_handles_insufficient_candles() -> None:
    settings = HistoricalReadSettings(lookback=5)

    report = analyze_historical_market(uptrend_candles()[:2], settings=settings)
    report_debug = report.to_debug_report(timeframe="1d")

    assert report.snapshot_debug_reports() == []
    assert report_debug["snapshot_count"] == 0
    assert report_debug["latest_snapshot"] is None
    assert report_debug["insufficient_data_reason"] == (
        "requires at least 5 candles to create a snapshot"
    )


def test_historical_snapshot_debug_report_handles_insufficient_context_fields() -> None:
    settings = HistoricalReadSettings(lookback=5, min_window=2, trend_strength=1)

    report = analyze_historical_market(uptrend_candles()[:2], settings=settings)
    snapshot_report = report.snapshot_debug_reports()[0]

    assert snapshot_report["ema_20"] is None
    assert snapshot_report["price_vs_ema_20"] == "unknown"
    assert snapshot_report["nearest_ma_support"] is None
    assert snapshot_report["nearest_ma_resistance"] is None
    assert snapshot_report["short_term_pressure"] == "unknown"
    assert snapshot_report["trend_condition"] == "unknown"
    assert snapshot_report["recent_return_pct"] is None
    assert "recent_return_unknown" in snapshot_report["unknown_reasons"]
    assert "ema_200_unknown" in snapshot_report["unknown_reasons"]
    assert snapshot_report["trend_fallback_reason"] == "insufficient_swing_structure"
    assert snapshot_report["insufficient_swing_structure"] is True


def test_historical_snapshot_uses_indicator_warmup_for_ema200() -> None:
    candles = steady_uptrend_candles(220)
    settings = HistoricalReadSettings(
        lookback=60,
        min_window=60,
        trend_strength=1,
    )

    report = analyze_historical_market(candles, settings=settings)
    first_snapshot = report.snapshot_debug_reports()[0]
    latest_snapshot = report.snapshot_debug_reports()[-1]

    assert first_snapshot["window_size"] == 60
    assert first_snapshot["indicator_window_size"] == 60
    assert first_snapshot["ema_20"] is not None
    assert first_snapshot["ema_50"] is not None
    assert first_snapshot["ema_200"] is None
    assert first_snapshot["price_vs_ema_200"] == "unknown"

    assert latest_snapshot["window_size"] == 60
    assert latest_snapshot["indicator_window_size"] == 220
    assert latest_snapshot["ema_20"] is not None
    assert latest_snapshot["ema_50"] is not None
    assert latest_snapshot["ema_200"] is not None
    assert latest_snapshot["price_vs_ema_200"] in {"above", "near"}


def test_historical_snapshot_indicator_warmup_does_not_expand_structural_window() -> None:
    candles = [*steady_uptrend_candles(210), *sideways_candles()]
    settings = HistoricalReadSettings(
        lookback=len(sideways_candles()),
        trend_strength=1,
    )

    report = analyze_historical_market(candles, settings=settings)
    latest_snapshot = report.snapshot_debug_reports()[-1]

    assert latest_snapshot["window_size"] == len(sideways_candles())
    assert latest_snapshot["indicator_window_size"] > latest_snapshot["window_size"]
    assert latest_snapshot["market_type"] == "trading_range"
    assert latest_snapshot["range_upper_bound"] == 112
    assert latest_snapshot["range_lower_bound"] == 98
    assert latest_snapshot["ema_200"] is not None


def test_historical_snapshot_debug_report_handles_sideways_candles() -> None:
    settings = HistoricalReadSettings(
        lookback=6,
        min_window=6,
        trend_strength=1,
        volume_average_period=3,
    )

    report = analyze_historical_market(sideways_candles(), settings=settings)
    snapshot_report = report.snapshot_debug_reports()[0]

    assert snapshot_report["bias"] == "sideways"
    assert snapshot_report["market_type"] == "trading_range"
    assert snapshot_report["trend_direction"] == "unknown"
    assert snapshot_report["trend_fallback_reason"] == "insufficient_swing_structure"
    assert "trend_unknown" in snapshot_report["unknown_reasons"]
    assert snapshot_report["range_upper_bound"] == 112
    assert snapshot_report["range_lower_bound"] == 98


def test_historical_snapshot_reports_true_sideways_without_directional_candidate() -> None:
    candles = mixed_sideways_structure_candles()
    settings = HistoricalReadSettings(
        lookback=len(candles),
        min_window=len(candles),
        trend_strength=1,
    )

    report = analyze_historical_market(candles, settings=settings)
    snapshot_report = report.snapshot_debug_reports()[0]

    assert snapshot_report["trend_direction"] == "sideways"
    assert snapshot_report["trend_candidate"] == "sideways"
    assert snapshot_report["messy_trend_candidate"] is False
    assert snapshot_report["trend_fallback_reason"] == "low_confidence_swing_structure"


def test_historical_snapshot_debug_report_handles_obvious_uptrend() -> None:
    settings = HistoricalReadSettings(
        lookback=9,
        min_window=9,
        trend_strength=1,
        volume_average_period=3,
    )

    report = analyze_historical_market(uptrend_candles(), settings=settings)
    snapshot_report = report.snapshot_debug_reports()[0]

    assert snapshot_report["bias"] == "bullish"
    assert snapshot_report["trend_direction"] == "uptrend"
    assert snapshot_report["trend_candidate"] == "uptrend"
    assert snapshot_report["trend_confidence"] == 1
    assert snapshot_report["latest_swing_high"]["price"] == 20
    assert snapshot_report["latest_swing_low"]["price"] == 10.5


def test_historical_snapshot_debug_report_handles_obvious_downtrend() -> None:
    settings = HistoricalReadSettings(
        lookback=9,
        min_window=9,
        trend_strength=1,
        volume_average_period=3,
    )

    report = analyze_historical_market(downtrend_candles(), settings=settings)
    snapshot_report = report.snapshot_debug_reports()[0]

    assert snapshot_report["bias"] == "bearish"
    assert snapshot_report["trend_direction"] == "downtrend"
    assert snapshot_report["trend_candidate"] == "downtrend"
    assert snapshot_report["trend_confidence"] == 1
    assert snapshot_report["latest_swing_high"]["price"] == 18
    assert snapshot_report["latest_swing_low"]["price"] == 10


def test_historical_snapshot_reports_uptrend_pullback_pressure_without_changing_trend() -> None:
    candles = broad_uptrend_with_recent_pullback_candles()
    settings = HistoricalReadSettings(
        lookback=len(candles),
        min_window=len(candles),
        trend_strength=1,
        volume_average_period=3,
    )

    report = analyze_historical_market(candles, settings=settings)
    snapshot_report = report.snapshot_debug_reports()[0]

    assert snapshot_report["trend_direction"] == "uptrend"
    assert snapshot_report["trend_confidence"] == 1
    assert snapshot_report["short_term_pressure"] == "bearish"
    assert snapshot_report["trend_condition"] == "pulling_back"
    assert snapshot_report["consecutive_down_closes"] == 4
    assert snapshot_report["recent_return_pct"] < 0
    assert snapshot_report["pullback_from_recent_high_pct"] > 0.05
    assert "recent_lower_closes" in snapshot_report["trend_health_reasons"]
    assert "sharp_pullback_from_recent_high" in snapshot_report["trend_health_reasons"]
    assert snapshot_report["market_read_status"] == "structural_uptrend_with_pullback"
    assert "Structural uptrend" in snapshot_report["market_read_summary"]
    assert "bearish_pressure" in snapshot_report["market_read_summary"]
    assert "pulling_back" in snapshot_report["market_read_summary"]
    assert snapshot_report["actionability"] == "watch_only"


def test_historical_snapshot_reports_testing_ema50_and_long_term_ma_context() -> None:
    candles = broad_uptrend_with_recent_pullback_candles()
    settings = HistoricalReadSettings(
        lookback=len(candles),
        min_window=len(candles),
        trend_strength=1,
        volume_average_period=3,
    )

    report = analyze_historical_market(candles, settings=settings)
    snapshot_report = report.snapshot_debug_reports()[0]

    assert snapshot_report["price_vs_ema_20"] == "below"
    assert snapshot_report["price_vs_ema_50"] == "near"
    assert snapshot_report["price_vs_ema_200"] == "above"
    assert snapshot_report["nearest_ma_support"]["name"] == "EMA200"
    assert any("ma_support EMA200" in level for level in snapshot_report["key_levels_summary"])
    assert "testing_ema50" in snapshot_report["trend_health_reasons"]
    assert "still_above_ema200" in snapshot_report["trend_health_reasons"]


def test_historical_snapshot_reports_messy_uptrend_candidate_without_changing_trend() -> None:
    candles = messy_directional_candles(direction=1)
    settings = HistoricalReadSettings(
        lookback=len(candles),
        min_window=len(candles),
        trend_strength=1,
    )

    report = analyze_historical_market(candles, settings=settings)
    snapshot_report = report.snapshot_debug_reports()[0]

    assert snapshot_report["trend_direction"] == "sideways"
    assert snapshot_report["trend_candidate"] == "uptrend"
    assert snapshot_report["messy_trend_candidate"] is True
    assert snapshot_report["messy_trend_direction"] == "up"
    assert snapshot_report["trend_fallback_reason"] == "low_confidence_swing_structure"
    assert snapshot_report["window_return_pct"] > 0
    assert "positive_window_return" in snapshot_report["trend_candidate_reasons"]
    assert "price_above_or_near_ema50" in snapshot_report["trend_candidate_reasons"]
    assert snapshot_report["trend_candidate_blocked_reason"] is None
    assert snapshot_report["trend_candidate_raw_score"] >= 3
    assert (
        snapshot_report["trend_candidate_effective_score"]
        >= snapshot_report["trend_candidate_threshold"]
    )
    assert (
        snapshot_report["trend_candidate_selected_score"]
        == snapshot_report["trend_candidate_effective_score"]
    )


def test_historical_snapshot_reports_messy_downtrend_candidate_without_changing_trend() -> None:
    candles = messy_directional_candles(direction=-1)
    settings = HistoricalReadSettings(
        lookback=len(candles),
        min_window=len(candles),
        trend_strength=1,
    )

    report = analyze_historical_market(candles, settings=settings)
    snapshot_report = report.snapshot_debug_reports()[0]

    assert snapshot_report["trend_direction"] == "sideways"
    assert snapshot_report["trend_candidate"] == "downtrend"
    assert snapshot_report["messy_trend_candidate"] is True
    assert snapshot_report["messy_trend_direction"] == "down"
    assert snapshot_report["trend_fallback_reason"] == "low_confidence_swing_structure"
    assert snapshot_report["window_return_pct"] < 0
    assert "negative_window_return" in snapshot_report["trend_candidate_reasons"]
    assert "price_below_ema200" in snapshot_report["trend_candidate_reasons"]
    assert snapshot_report["trend_candidate_blocked_reason"] is None
    assert (
        snapshot_report["trend_candidate_effective_score"]
        >= snapshot_report["trend_candidate_threshold"]
    )
    assert (
        snapshot_report["market_read_status"]
        == "structural_sideways_with_messy_downtrend_candidate"
    )
    assert "messy downtrend candidate" in snapshot_report["market_read_summary"]


def test_historical_snapshot_blocks_small_upward_range_candidate() -> None:
    candles = ko_like_range_candles(direction=1)
    settings = HistoricalReadSettings(
        lookback=len(candles),
        min_window=len(candles),
        trend_strength=1,
    )

    report = analyze_historical_market(candles, settings=settings)
    snapshot_report = report.snapshot_debug_reports()[0]

    assert snapshot_report["market_type"] == "trading_range"
    assert snapshot_report["trend_candidate"] == "sideways"
    assert snapshot_report["messy_trend_candidate"] is False
    assert snapshot_report["trend_candidate_blocked_reason"] == (
        "range_market_without_breakout_evidence"
    )
    assert snapshot_report["trend_candidate_raw_score"] >= 2
    assert snapshot_report["trend_candidate_selected_score"] == 0
    assert "up:positive_window_return" in snapshot_report["trend_candidate_raw_reasons"]
    assert snapshot_report["market_read_status"] == "trading_range"
    assert "Trading range" in snapshot_report["market_read_summary"]
    assert "range_bound" in snapshot_report["caution_notes"]


def test_historical_snapshot_blocks_small_downward_range_candidate() -> None:
    candles = ko_like_range_candles(direction=-1)
    settings = HistoricalReadSettings(
        lookback=len(candles),
        min_window=len(candles),
        trend_strength=1,
    )

    report = analyze_historical_market(candles, settings=settings)
    snapshot_report = report.snapshot_debug_reports()[0]

    assert snapshot_report["market_type"] == "trading_range"
    assert snapshot_report["trend_candidate"] == "sideways"
    assert snapshot_report["messy_trend_candidate"] is False
    assert snapshot_report["trend_candidate_blocked_reason"] == (
        "range_market_without_breakout_evidence"
    )
    assert snapshot_report["trend_candidate_raw_score"] >= 2
    assert snapshot_report["trend_candidate_selected_score"] == 0
    assert "down:negative_window_return" in snapshot_report["trend_candidate_raw_reasons"]


def test_historical_snapshot_reports_candidate_pressure_conflicts() -> None:
    candles = broad_uptrend_with_recent_pullback_candles()
    settings = HistoricalReadSettings(
        lookback=len(candles),
        min_window=len(candles),
        trend_strength=1,
        volume_average_period=3,
    )

    report = analyze_historical_market(candles, settings=settings)
    snapshot_report = report.snapshot_debug_reports()[0]

    assert snapshot_report["trend_direction"] == "uptrend"
    assert snapshot_report["short_term_pressure"] == "bearish"
    assert snapshot_report["trend_candidate"] == "uptrend"
    assert (
        snapshot_report["trend_candidate_raw_score"] > snapshot_report["trend_candidate_threshold"]
    )
    assert (
        snapshot_report["trend_candidate_effective_score"]
        >= snapshot_report["trend_candidate_threshold"]
    )
    assert (
        snapshot_report["trend_candidate_selected_score"]
        == snapshot_report["trend_candidate_effective_score"]
    )
    assert snapshot_report["trend_candidate_blocked_reason"] is None
    assert snapshot_report["trend_candidate_conflict_count"] > 0
    assert "bearish_pressure_conflict" in snapshot_report["trend_candidate_conflicts"]


def test_historical_snapshot_summary_uses_neutral_language() -> None:
    reports = [
        analyze_historical_market(
            broad_uptrend_with_recent_pullback_candles(),
            settings=HistoricalReadSettings(
                lookback=220,
                min_window=220,
                trend_strength=1,
            ),
        ).snapshot_debug_reports()[0],
        analyze_historical_market(
            messy_directional_candles(direction=-1),
            settings=HistoricalReadSettings(
                lookback=len(messy_directional_candles(direction=-1)),
                min_window=len(messy_directional_candles(direction=-1)),
                trend_strength=1,
            ),
        ).snapshot_debug_reports()[0],
        analyze_historical_market(
            ko_like_range_candles(direction=1),
            settings=HistoricalReadSettings(
                lookback=len(ko_like_range_candles(direction=1)),
                min_window=len(ko_like_range_candles(direction=1)),
                trend_strength=1,
            ),
        ).snapshot_debug_reports()[0],
    ]

    blocked_words = {"buy", "sell", "short"}
    for report in reports:
        summary_values = [
            report["market_read_status"],
            report["market_read_summary"],
            report["actionability"],
            *report["caution_notes"],
            *report["key_levels_summary"],
        ]
        summary_text = " ".join(str(value).lower() for value in summary_values)
        assert not blocked_words.intersection(summary_text.split())


def test_historical_market_read_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="candles"):
        analyze_historical_market([])

    with pytest.raises(ValueError, match="lookback"):
        HistoricalReadSettings(lookback=1)

    with pytest.raises(ValueError, match="step"):
        HistoricalReadSettings(step=0)

    with pytest.raises(ValueError, match="min_window"):
        HistoricalReadSettings(lookback=5, min_window=6)
