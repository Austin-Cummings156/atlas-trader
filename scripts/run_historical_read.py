"""Run a historical market-reading report for one symbol."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from math import isfinite
from pathlib import Path
from typing import Any

import yfinance as yf
from rich.console import Console
from rich.table import Table

from atlas_trader.backtesting import HistoricalReadSettings, analyze_historical_market
from atlas_trader.data.models import Candle


def main() -> None:
    """Fetch historical candles and print a market-reading summary."""
    args = _parse_args()
    candles = _fetch_candles(args.symbol, args.period, args.interval)
    settings = HistoricalReadSettings(
        lookback=args.lookback,
        step=args.step,
        trend_strength=args.trend_strength,
        support_resistance_strength=args.support_resistance_strength,
        volume_average_period=args.volume_average_period,
    )
    report = analyze_historical_market(candles, settings=settings)
    if args.audit_csv:
        _write_audit_csv(
            report,
            Path(args.audit_csv),
            timeframe=args.interval,
            events_only=not args.full_audit,
            include_level_events=args.include_level_events,
        )
    _print_report(
        report,
        timeframe=args.interval,
        audit_limit=args.audit_limit,
        include_level_events=args.include_level_events,
        tail=args.tail,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="AAPL", help="Symbol to read, such as AAPL or SPY.")
    parser.add_argument("--period", default="2y", help="yfinance period, such as 6mo, 1y, or 2y.")
    parser.add_argument("--interval", default="1d", help="yfinance interval, such as 1d or 1wk.")
    parser.add_argument("--lookback", type=int, default=60, help="Rolling candle lookback.")
    parser.add_argument("--step", type=int, default=1, help="Snapshot step size in candles.")
    parser.add_argument("--trend-strength", type=int, default=None)
    parser.add_argument("--support-resistance-strength", type=int, default=None)
    parser.add_argument("--volume-average-period", type=int, default=None)
    parser.add_argument("--audit-limit", type=int, default=20, help="Audit rows to print.")
    parser.add_argument(
        "--tail",
        type=int,
        default=0,
        help="Print the latest N structured snapshot summaries.",
    )
    parser.add_argument("--audit-csv", help="Optional path for audit CSV output.")
    parser.add_argument(
        "--full-audit",
        action="store_true",
        help="Write every snapshot to CSV instead of only interesting audit events.",
    )
    parser.add_argument(
        "--include-level-events",
        action="store_true",
        help="Include near support/resistance events in audit output.",
    )
    return parser.parse_args()


def _fetch_candles(symbol: str, period: str, interval: str) -> list[Candle]:
    ticker = yf.Ticker(symbol)
    data = ticker.history(period=period, interval=interval, auto_adjust=False)
    if data.empty:
        raise ValueError(f"No historical data returned for {symbol}.")

    candles: list[Candle] = []
    for timestamp, row in data.iterrows():
        open_price = _row_value(row, "Open")
        high = _row_value(row, "High")
        low = _row_value(row, "Low")
        close = _row_value(row, "Close")
        volume = _row_value(row, "Volume")
        if None in {open_price, high, low, close, volume}:
            continue

        candles.append(
            Candle(
                symbol=symbol.upper(),
                timestamp=_to_datetime(timestamp),
                open=float(open_price),
                high=float(high),
                low=float(low),
                close=float(close),
                volume=float(volume),
            )
        )

    if not candles:
        raise ValueError(f"No usable candles returned for {symbol}.")

    return candles


def _row_value(row: Any, key: str) -> float | None:
    value = row.get(key)
    if value is None:
        return None
    numeric_value = float(value)
    return numeric_value if isfinite(numeric_value) else None


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    return value.to_pydatetime().replace(tzinfo=None)


def _print_report(
    report: Any,
    *,
    timeframe: str | None,
    audit_limit: int,
    include_level_events: bool,
    tail: int,
) -> None:
    console = Console()
    latest = report.latest_snapshot
    audit_events = report.audit_events(include_level_events=include_level_events)

    console.print(f"[bold]{report.symbol} historical market read[/bold]")
    console.print(
        f"Candles: {len(report.candles)} | Snapshots: {report.snapshot_count} | "
        f"Lookback: {report.settings.lookback}"
    )

    if latest is not None:
        latest_report = latest.to_debug_report(timeframe=timeframe)
        console.print(
            "Latest: "
            f"{latest_report['candle_date']} close={latest_report['latest_close']:.2f} "
            f"bias={latest_report['bias']} trend={latest_report['trend_direction']} "
            f"market={latest_report['market_type']}"
        )

    table = Table(title="Historical Read Counts")
    table.add_column("Category")
    table.add_column("Counts")
    table.add_row("Trend", _format_counts(report.trend_counts))
    table.add_row("Market Type", _format_counts(report.market_type_counts))
    table.add_row("Breakouts", _format_counts(report.breakout_counts))
    table.add_row("Bias", _format_counts(report.bias_counts))
    table.add_row("High Relative Volume", str(report.high_relative_volume_count))
    table.add_row("Confirmed Breakout Volume", str(report.confirmed_breakout_count))
    console.print(table)

    if audit_limit > 0:
        audit_table = Table(title=f"Audit Events First {audit_limit}")
        audit_table.add_column("Date")
        audit_table.add_column("Close")
        audit_table.add_column("Bias")
        audit_table.add_column("Trend")
        audit_table.add_column("Market")
        audit_table.add_column("Breakout")
        audit_table.add_column("Volume")
        audit_table.add_column("Reasons")

        for event in audit_events[:audit_limit]:
            snapshot = event.snapshot
            audit_table.add_row(
                event.date,
                f"{snapshot.close:.2f}",
                str(snapshot.bias),
                str(snapshot.trend.direction),
                str(snapshot.sideways_market.market_type),
                str(snapshot.sideways_market.breakout_direction),
                str(snapshot.volume.relative_volume_level),
                ", ".join(str(reason) for reason in event.reasons),
            )
        console.print(audit_table)
        console.print(f"Audit events: {len(audit_events)}")

    if tail > 0:
        snapshot_table = Table(title=f"Latest {tail} Snapshot Reports")
        snapshot_table.add_column("Date")
        snapshot_table.add_column("Close")
        snapshot_table.add_column("Bias")
        snapshot_table.add_column("Trend")
        snapshot_table.add_column("Conf")
        snapshot_table.add_column("Market")
        snapshot_table.add_column("Vol")
        snapshot_table.add_column("Pressure")
        snapshot_table.add_column("Condition")
        snapshot_table.add_column("Candidate")
        snapshot_table.add_column("MA Context")
        snapshot_table.add_column("Support")
        snapshot_table.add_column("Resistance")
        snapshot_table.add_column("Volume")
        snapshot_table.add_column("Unknowns")

        for snapshot_report in report.snapshot_debug_reports(
            tail=tail,
            timeframe=timeframe,
        ):
            snapshot_table.add_row(
                str(snapshot_report["candle_date"]),
                f"{snapshot_report['latest_close']:.2f}",
                str(snapshot_report["bias"]),
                str(snapshot_report["trend_direction"]),
                f"{snapshot_report['trend_confidence']:.2f}",
                str(snapshot_report["market_type"]),
                str(snapshot_report["volatility_level"]),
                str(snapshot_report["short_term_pressure"]),
                str(snapshot_report["trend_condition"]),
                _format_candidate(snapshot_report),
                _format_ma_context(snapshot_report),
                _format_optional_price(snapshot_report["nearest_support_price"]),
                _format_optional_price(snapshot_report["nearest_resistance_price"]),
                str(snapshot_report["relative_volume_level"]),
                ", ".join(snapshot_report["unknown_reasons"]),
            )
        console.print(snapshot_table)


def _write_audit_csv(
    report: Any,
    path: Path,
    *,
    timeframe: str | None,
    events_only: bool,
    include_level_events: bool,
) -> None:
    rows = (
        [
            _audit_row(event.snapshot, event.reasons, timeframe=timeframe)
            for event in report.audit_events(include_level_events=include_level_events)
        ]
        if events_only
        else [_audit_row(snapshot, [], timeframe=timeframe) for snapshot in report.snapshots]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(_audit_fieldnames()))
        writer.writeheader()
        writer.writerows(rows)


def _audit_fieldnames() -> tuple[str, ...]:
    return (
        "date",
        "close",
        "bias",
        "trend",
        "trend_confidence",
        "market_type",
        "breakout",
        "relative_volume",
        "volume_trend",
        "breakout_volume",
        "nearest_support",
        "nearest_resistance",
        "reasons",
    )


def _audit_row(
    snapshot: Any,
    reasons: list[Any],
    *,
    timeframe: str | None,
) -> dict[str, str | float | None]:
    snapshot_report = snapshot.to_debug_report(timeframe=timeframe, reasons=reasons)
    return {
        "date": snapshot_report["candle_date"],
        "close": round(snapshot_report["latest_close"], 4),
        "bias": snapshot_report["bias"],
        "trend": snapshot_report["trend_direction"],
        "trend_confidence": snapshot_report["trend_confidence"],
        "market_type": snapshot_report["market_type"],
        "breakout": snapshot_report["breakout_direction"],
        "relative_volume": snapshot_report["relative_volume_level"],
        "volume_trend": snapshot_report["volume_trend"],
        "breakout_volume": snapshot_report["breakout_volume_context"],
        "nearest_support": _round_optional_price(snapshot_report["nearest_support_price"]),
        "nearest_resistance": _round_optional_price(snapshot_report["nearest_resistance_price"]),
        "reasons": "|".join(snapshot_report["audit_reasons"]),
    }


def _format_counts(counts: dict[Any, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}: {value}" for key, value in counts.items())


def _round_optional_price(value: Any) -> float | None:
    return round(value, 4) if value is not None else None


def _format_optional_price(value: Any) -> str:
    return f"{value:.2f}" if value is not None else "-"


def _format_ma_context(snapshot_report: dict[str, Any]) -> str:
    nearest_support = snapshot_report["nearest_ma_support"]
    nearest_resistance = snapshot_report["nearest_ma_resistance"]
    if nearest_support:
        return f"{nearest_support['name']} support"
    if nearest_resistance:
        return f"{nearest_resistance['name']} resistance"
    return (
        f"20:{snapshot_report['price_vs_ema_20']} "
        f"50:{snapshot_report['price_vs_ema_50']} "
        f"200:{snapshot_report['price_vs_ema_200']}"
    )


def _format_candidate(snapshot_report: dict[str, Any]) -> str:
    candidate = snapshot_report["trend_candidate"]
    if snapshot_report["messy_trend_candidate"]:
        return f"messy_{candidate}"
    return str(candidate)


if __name__ == "__main__":
    main()
