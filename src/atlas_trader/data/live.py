"""Live market-data loading helpers."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Any

import pandas as pd

from atlas_trader.data.models import Candle


class MarketDataError(RuntimeError):
    """Raised when market data cannot be loaded."""


@dataclass(frozen=True)
class LiveTimeframeSpec:
    """Provider request and local aggregation settings for one timeframe."""

    name: str
    period: str
    interval: str
    resample_rule: str | None = None

    def __post_init__(self) -> None:
        """Validate timeframe fetch settings."""
        if not self.name.strip():
            raise ValueError("name must not be blank.")
        if not self.period.strip():
            raise ValueError("period must not be blank.")
        if not self.interval.strip():
            raise ValueError("interval must not be blank.")
        if self.resample_rule is not None and not self.resample_rule.strip():
            raise ValueError("resample_rule must not be blank.")


DEFAULT_SWING_POSITION_TIMEFRAMES: tuple[LiveTimeframeSpec, ...] = (
    LiveTimeframeSpec(name="4h", period="730d", interval="1h", resample_rule="4h"),
    LiveTimeframeSpec(name="1d", period="2y", interval="1d"),
    LiveTimeframeSpec(name="1wk", period="5y", interval="1wk"),
)


def fetch_timeframe_candles(
    symbol: str,
    spec: LiveTimeframeSpec,
    *,
    ticker_factory: Callable[[str], Any] | None = None,
) -> list[Candle]:
    """Fetch candles for a symbol and timeframe spec."""
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol must not be blank.")

    ticker = _build_ticker(normalized_symbol, ticker_factory)
    try:
        data = ticker.history(period=spec.period, interval=spec.interval, auto_adjust=False)
    except Exception as exc:
        message = f"Could not fetch {spec.name} candles for {normalized_symbol}."
        raise MarketDataError(message) from exc

    if data is None or getattr(data, "empty", True):
        raise MarketDataError(f"No {spec.name} candles returned for {normalized_symbol}.")

    normalized_data = _normalize_history_frame(data)
    if spec.resample_rule:
        normalized_data = _resample_history_frame(normalized_data, spec.resample_rule)

    candles = _frame_to_candles(normalized_symbol, normalized_data)
    if not candles:
        raise MarketDataError(f"No usable {spec.name} candles returned for {normalized_symbol}.")
    return candles


def fetch_multi_timeframe_candles(
    symbol: str,
    *,
    specs: Sequence[LiveTimeframeSpec] = DEFAULT_SWING_POSITION_TIMEFRAMES,
    ticker_factory: Callable[[str], Any] | None = None,
) -> dict[str, list[Candle]]:
    """Fetch all configured timeframes for one symbol."""
    if not specs:
        raise ValueError("specs must contain at least one timeframe.")

    return {
        spec.name: fetch_timeframe_candles(symbol, spec, ticker_factory=ticker_factory)
        for spec in specs
    }


def _build_ticker(symbol: str, ticker_factory: Callable[[str], Any] | None) -> Any:
    if ticker_factory is not None:
        return ticker_factory(symbol)

    try:
        import yfinance as yf
    except ImportError as exc:
        raise MarketDataError("yfinance is required to fetch market data.") from exc

    return yf.Ticker(symbol)


def _normalize_history_frame(data: Any) -> pd.DataFrame:
    frame = pd.DataFrame(data).copy()
    if frame.empty:
        return frame

    if not isinstance(frame.index, pd.DatetimeIndex):
        frame.index = pd.to_datetime(frame.index)
    if frame.index.tz is not None:
        frame.index = frame.index.tz_convert(None)
    return frame.sort_index()


def _resample_history_frame(data: pd.DataFrame, rule: str) -> pd.DataFrame:
    if data.empty:
        return data

    aggregations = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }
    available = {key: value for key, value in aggregations.items() if key in data.columns}
    if set(available) != set(aggregations):
        return pd.DataFrame()

    return data.resample(rule, label="right", closed="right").agg(available).dropna()


def _frame_to_candles(symbol: str, data: pd.DataFrame) -> list[Candle]:
    required_columns = {"Open", "High", "Low", "Close", "Volume"}
    if data.empty or not required_columns.issubset(data.columns):
        return []

    candles: list[Candle] = []
    for timestamp, row in data.iterrows():
        open_price = _finite_row_value(row, "Open")
        high = _finite_row_value(row, "High")
        low = _finite_row_value(row, "Low")
        close = _finite_row_value(row, "Close")
        volume = _finite_row_value(row, "Volume")
        if None in {open_price, high, low, close, volume}:
            continue

        try:
            candles.append(
                Candle(
                    symbol=symbol,
                    timestamp=_to_datetime(timestamp),
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )
        except ValueError:
            continue

    return candles


def _finite_row_value(row: Any, key: str) -> float | None:
    value = row.get(key)
    if value is None:
        return None
    numeric_value = float(value)
    return numeric_value if isfinite(numeric_value) else None


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    return value.to_pydatetime().replace(tzinfo=None)
