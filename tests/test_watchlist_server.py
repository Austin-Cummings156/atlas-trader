"""Tests for the watchlist server runner."""

from datetime import datetime

import pandas as pd

from atlas_trader.server import WatchlistServerSettings, run_watchlist_cycle


class FakeTicker:
    def history(self, *, period: str, interval: str, auto_adjust: bool) -> pd.DataFrame:
        if interval == "1h":
            return _history_frame("2026-01-01", periods=260, freq="h", start_price=100)
        if interval == "1d":
            return _history_frame("2025-01-01", periods=260, freq="D", start_price=95)
        return _history_frame("2022-01-01", periods=220, freq="W", start_price=80)


def test_run_watchlist_cycle_writes_review_artifacts(tmp_path) -> None:
    settings = WatchlistServerSettings(
        symbols=("TEST",),
        output_dir=tmp_path,
        max_cycles=1,
    )

    result = run_watchlist_cycle(
        settings,
        ticker_factory=lambda symbol: FakeTicker(),
        generated_at=datetime(2026, 6, 26, 12, 0, 0),
    )

    assert len(result.reports) == 1
    assert result.errors == []
    assert result.reports[0]["symbol"] == "TEST"
    assert result.reports[0]["actionability"] == "watch_only"
    assert result.reports[0]["timeframes"].keys() == {"4h", "1d", "1wk"}
    assert result.json_path is not None and result.json_path.exists()
    assert result.csv_path is not None and result.csv_path.exists()
    assert result.pdf_path is not None and result.pdf_path.exists()
    assert result.pdf_path.read_bytes().startswith(b"%PDF-1.4")


def _history_frame(start: str, *, periods: int, freq: str, start_price: float) -> pd.DataFrame:
    dates = pd.date_range(start, periods=periods, freq=freq)
    rows = []
    for index in range(periods):
        close = start_price + index * 0.5
        rows.append(
            {
                "Open": close - 0.2,
                "High": close + 1.0,
                "Low": close - 1.0,
                "Close": close,
                "Volume": 1000 + index,
            }
        )
    return pd.DataFrame(rows, index=dates)
