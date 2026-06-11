"""Tests for the historical-read CLI helpers."""

import json
import sys
from datetime import datetime, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from math import inf, nan
from pathlib import Path
from types import ModuleType

from atlas_trader.backtesting import HistoricalReadSettings, analyze_historical_market
from atlas_trader.data.models import Candle


def load_script_module() -> ModuleType:
    script_path = Path(__file__).parents[1] / "scripts" / "run_historical_read.py"
    spec = spec_from_file_location("run_historical_read", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_candle(index: int, *, close: float) -> Candle:
    return Candle(
        symbol="TEST",
        timestamp=datetime(2026, 1, 1) + timedelta(days=index),
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=1000 + index,
    )


def debug_report() -> object:
    candles = [make_candle(index, close=100 + index) for index in range(220)]
    return analyze_historical_market(
        candles,
        settings=HistoricalReadSettings(
            lookback=len(candles),
            min_window=len(candles),
            trend_strength=1,
        ),
    )


def test_row_value_skips_missing_and_non_finite_values() -> None:
    script = load_script_module()

    assert script._row_value({"Open": None}, "Open") is None
    assert script._row_value({"Open": nan}, "Open") is None
    assert script._row_value({"Open": inf}, "Open") is None
    assert script._row_value({"Open": "-inf"}, "Open") is None
    assert script._row_value({"Open": "123.45"}, "Open") == 123.45


def test_debug_tail_json_includes_detailed_report_fields() -> None:
    script = load_script_module()

    output = script._debug_tail_json(debug_report(), timeframe="1d", debug_tail=1)
    reports = json.loads(output)

    assert len(reports) == 1
    latest = reports[0]
    assert latest["symbol"] == "TEST"
    assert latest["timeframe"] == "1d"
    assert "trend_candidate" in latest
    assert "trend_candidate_raw_score" in latest
    assert "trend_candidate_conflict_count" in latest
    assert "trend_candidate_effective_score" in latest
    assert "trend_candidate_threshold" in latest
    assert "trend_candidate_selected_score" in latest
    assert "trend_candidate_blocked_reason" in latest
    assert "trend_candidate_raw_reasons" in latest
    assert "trend_candidate_conflicts" in latest
    assert "trend_candidate_reasons" in latest
    assert "window_return_pct" in latest
    assert "short_term_pressure" in latest
    assert "trend_condition" in latest
    assert "market_type" in latest
    assert "volatility_level" in latest
    assert "price_vs_ema_50" in latest
    assert "nearest_support" in latest
    assert "trend_fallback_reason" in latest
    assert "confirmed_swing_high_count" in latest
    assert "market_read_status" in latest
    assert "market_read_summary" in latest
    assert "caution_notes" in latest
    assert "key_levels_summary" in latest
    assert latest["actionability"] == "watch_only"


def test_debug_tail_json_zero_is_empty_list() -> None:
    script = load_script_module()

    assert script._debug_tail_json(debug_report(), timeframe="1d", debug_tail=0) == "[]"


def test_parse_args_accepts_debug_tail(monkeypatch) -> None:
    script = load_script_module()
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_historical_read.py", "--symbol", "NVDA", "--debug-tail", "3"],
    )

    args = script._parse_args()

    assert args.symbol == "NVDA"
    assert args.debug_tail == 3
