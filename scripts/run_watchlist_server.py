"""Run AtlasTrader watchlist market reads on a schedule."""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from atlas_trader.analysis import MultiTimeframeSettings
from atlas_trader.server import WatchlistServerSettings, run_watchlist_server


def main() -> None:
    """Run the watchlist server CLI."""
    args = _parse_args()
    settings = WatchlistServerSettings(
        symbols=tuple(_parse_symbols(args.symbols)),
        output_dir=Path(args.output_dir),
        poll_seconds=args.poll_seconds,
        max_cycles=1 if args.once else args.max_cycles,
        multi_timeframe_settings=MultiTimeframeSettings(
            recent_timeframe="4h",
            primary_timeframe="1d",
            long_term_timeframe="1wk",
            trend_strength=args.trend_strength,
            support_resistance_strength=args.support_resistance_strength,
            volume_average_period=args.volume_average_period,
        ),
        write_pdf=not args.no_pdf,
        write_json=not args.no_json,
        write_csv=not args.no_csv,
    )
    console = Console()
    console.print(
        f"[bold]AtlasTrader watchlist server[/bold] symbols={', '.join(settings.symbols)} "
        f"poll_seconds={settings.poll_seconds} max_cycles={settings.max_cycles or 'forever'}"
    )
    results = run_watchlist_server(settings)
    for result in results:
        console.print(
            f"cycle={result.generated_at.isoformat()} reports={len(result.reports)} "
            f"errors={len(result.errors)} json={result.json_path} pdf={result.pdf_path}"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--symbols",
        default="AAPL,MSFT,NVDA,SPY",
        help="Comma-separated symbols to monitor.",
    )
    parser.add_argument("--output-dir", default="runtime/watchlist")
    parser.add_argument("--poll-seconds", type=int, default=60 * 60)
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one cycle and exit. Useful for testing before background operation.",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help="Stop after this many cycles. Omit for continuous operation.",
    )
    parser.add_argument("--trend-strength", type=int, default=None)
    parser.add_argument("--support-resistance-strength", type=int, default=None)
    parser.add_argument("--volume-average-period", type=int, default=None)
    parser.add_argument("--no-pdf", action="store_true")
    parser.add_argument("--no-json", action="store_true")
    parser.add_argument("--no-csv", action="store_true")
    return parser.parse_args()


def _parse_symbols(value: str) -> list[str]:
    symbols = [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]
    if not symbols:
        raise ValueError("--symbols must contain at least one symbol.")
    return symbols


if __name__ == "__main__":
    main()
