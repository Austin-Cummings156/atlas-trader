"""Tests for live market-data helpers."""

import pandas as pd
import pytest

from atlas_trader.data.live import LiveTimeframeSpec, MarketDataError, fetch_timeframe_candles


class FakeTicker:
    def history(self, *, period: str, interval: str, auto_adjust: bool) -> pd.DataFrame:
        index = pd.date_range("2026-01-01 09:00", periods=8, freq="h")
        return pd.DataFrame(
            {
                "Open": [100, 101, 102, 103, 104, 105, 106, 107],
                "High": [101, 102, 103, 104, 105, 106, 107, 108],
                "Low": [99, 100, 101, 102, 103, 104, 105, 106],
                "Close": [100.5, 101.5, 102.5, 103.5, 104.5, 105.5, 106.5, 107.5],
                "Volume": [10, 20, 30, 40, 50, 60, 70, 80],
            },
            index=index,
        )


class EmptyTicker:
    def history(self, *, period: str, interval: str, auto_adjust: bool) -> pd.DataFrame:
        return pd.DataFrame()


def test_fetch_timeframe_candles_resamples_intraday_data() -> None:
    candles = fetch_timeframe_candles(
        "aapl",
        LiveTimeframeSpec(name="4h", period="5d", interval="1h", resample_rule="4h"),
        ticker_factory=lambda symbol: FakeTicker(),
    )

    assert len(candles) == 2
    assert candles[0].symbol == "AAPL"
    assert candles[0].open == pytest.approx(100)
    assert candles[0].high == pytest.approx(104)
    assert candles[0].low == pytest.approx(99)
    assert candles[0].close == pytest.approx(103.5)
    assert candles[0].volume == pytest.approx(100)


def test_fetch_timeframe_candles_rejects_empty_provider_data() -> None:
    with pytest.raises(MarketDataError, match="No 1d candles"):
        fetch_timeframe_candles(
            "AAPL",
            LiveTimeframeSpec(name="1d", period="1y", interval="1d"),
            ticker_factory=lambda symbol: EmptyTicker(),
        )
