# AtlasTrader

AtlasTrader is a Python market-analysis, validation, and trading-research system focused
first on swing and position trading. It is currently a research and market-reading
validation project, not a live trading bot.

The current goal is to build a market reader that can explain what it sees in historical
and current chart context before it is trusted for paper trading or live automation.
Day-trading research may be added later, but the near-term system is being designed around
slower swing and position workflows that can be reviewed without constant screen-watching.

AtlasTrader does not currently place real trades, send live alerts, or connect to a broker.

## Current Status

Version: `0.7.0a1` in progress

The v0.7 focus is historical market-reading validation and structured debug reporting. The
project has moved beyond basic candle reading and now produces layered chart-reading context
that can be compared against real charts.

Current market-reading/reporting support includes:

- Candle analysis and candle context
- Trend, range, consolidation, and congestion analysis
- Support and resistance context
- Volume context and breakout-volume context
- Volatility context
- EMA 20/50/200 context with indicator warmup for rolling historical snapshots
- Short-term pressure and trend-condition reporting
- Trend evidence, candidate direction, score, conflict, and blocked-reason reporting
- Structured per-snapshot debug reports
- Rolling historical validation over candle windows
- CLI summary tables with `--tail`
- Full recent snapshot JSON output with `--debug-tail`
- Concise market-read summaries for future watchlist/notification work
- Deterministic synthetic tests that avoid network calls

The final structural trend/range labels are intentionally conservative. Additional report
fields are used to explain pullbacks, messy directional candidates, range guardrails, EMA
context, pressure, and conflicts without promoting those fields into final trade decisions.

## Project Direction

AtlasTrader is being built in stages:

1. Finish and clean the current market-reading/reporting foundation.
   The system should explain what it sees before it is trusted to trade. Structured reports
   are used to visually verify market reads against charts while keeping final trend/range
   labels conservative.

2. Repair and improve fundamentals analysis.
   Fundamentals should help narrow the tradable universe and decide what symbols are worth
   monitoring. It should act as a filter and context layer, not a replacement for chart
   analysis.

3. Add server/watchlist operation.
   After fundamentals are repaired, AtlasTrader should be able to run on a local machine,
   server, or homelab; monitor a configured watchlist or filtered symbol universe; run on
   scheduled intervals such as daily and eventually 4H; save market-read results locally;
   and emit watch-only reports when relevant conditions are detected.

4. Add a paper trading engine.
   Paper trading should simulate swing and position trades first, including entries, exits,
   stop losses, targets, risk/reward, exposure, win/loss, drawdown, and performance over
   time. Realistic assumptions for slippage, fees, and incomplete fills should be added
   where practical.

5. Add live trading later.
   Live trading should only come after extensive paper validation, strong safety controls,
   and broker-integration testing.

6. Research day trading later.
   The architecture should not block future intraday research, but reliable swing/position
   workflows are the priority before day-trading support.

## Roadmap

- v0.1: Project setup
- v0.2: Candle reader
- v0.3: Trend, range, and consolidation detection
- v0.4: Support, resistance, and volume context
- v0.5: Multi-timeframe analysis
- v0.6: Fundamentals reader
- v0.7: Historical market-reading validation and structured debug reports
- v0.8: Fundamentals repair and symbol filtering
- v0.9: Server/watchlist runner and watch-only notifications
- v0.10: Paper trading engine for swing/position strategies
- v0.11+: Live trading safety layer and broker integration, only after paper validation
- Later: Day-trading research and intraday strategy support

## CLI Usage

Run a historical market read for a symbol:

```bash
python scripts/run_historical_read.py --symbol AAPL --period 2y --interval 1d
```

Show recent structured snapshot summaries:

```bash
python scripts/run_historical_read.py --symbol AAPL --period 2y --interval 1d --tail 10
```

Show a concise table plus full JSON debug reports for the latest snapshots:

```bash
python scripts/run_historical_read.py \
  --symbol NVDA \
  --period 2y \
  --interval 1d \
  --tail 20 \
  --debug-tail 5
```

Useful manual comparison commands:

```bash
python scripts/run_historical_read.py --symbol MSFT --period 2y --interval 1d --tail 20 --debug-tail 5
python scripts/run_historical_read.py --symbol TSLA --period 2y --interval 1d --tail 20 --debug-tail 5
python scripts/run_historical_read.py --symbol SPY --period 2y --interval 1d --tail 20 --debug-tail 5
python scripts/run_historical_read.py --symbol KO --period 2y --interval 1d --tail 20 --debug-tail 5
```

The historical CLI may use `yfinance` to download data for local research and visual chart
comparison. Tests use deterministic synthetic candles and should not require internet access
or live data downloads.

## Implemented Analysis Areas

### Candle Reader

The candle reader provides tested building blocks for chart structure work:

- OHLCV candle validation
- Candle direction
- Candle body, range, and wick measurements
- Candle strength classification
- Indecision and long-wick classification
- Close-position classification
- Previous-candle comparisons
- Inside bar and outside bar detection
- Rolling range context

### Market Structure

Current market-structure analysis supports:

- Confirmed swing high and swing low detection
- Uptrend detection from higher highs and higher lows
- Downtrend detection from lower highs and lower lows
- Sideways classification for mixed or weak swing structure
- Trading range detection from repeated support and resistance touches
- Congestion detection for tight overlapping price action
- Consolidation detection for bounded sideways pauses
- Prior-window breakout direction checks
- Immutable settings objects for analysis thresholds

### Support, Resistance, and Volume

Current support/resistance and volume analysis supports:

- Support and resistance detection from clustered swing lows and highs
- Nearest support and nearest resistance lookup around the latest close
- Level touch counts, price zones, distance from close, and confidence scores
- Rolling volume average
- Relative-volume classification
- Volume-trend classification
- Breakout-volume context

### Multi-Timeframe Analysis

Current multi-timeframe analysis supports:

- Individual timeframe summaries that compose trend, range, support/resistance, and volume
  analysis
- Timeframe roles for recent, primary, long-term, and supporting context
- Default swing/position roles for 4H, 1D, and 1Y candles
- Directional bias and alignment classification
- Weighted confidence and directional conflict reporting

### Fundamentals

The current fundamentals layer is data-only and needs repair before server/watchlist
operation. The intended role of fundamentals is to help filter and rank symbols for
monitoring, not to replace chart analysis.

Existing fundamentals work includes classifications for:

- Growth and performance context
- Quarterly EPS trend
- P/E valuation context
- Debt load
- Profitability
- Overall score, data quality, and rating

### Historical Validation and Debug Reports

The v0.7 historical reader walks historical candles chronologically and runs market readers
over rolling windows to check whether AtlasTrader can describe market structure coherently.
It is validation/debug infrastructure, not profit/loss backtesting.

Current historical validation supports:

- Rolling historical snapshots over a configurable candle lookback
- Separate indicator warmup history for EMA context
- Per-snapshot trend, range, support/resistance, volume, volatility, EMA, pressure, and
  trend-candidate reports
- Candidate score, conflict, threshold, selected-score, and blocked-reason fields
- Summary counts for trend direction, market type, breakout direction, and bias
- Concise market-read summary fields for future notification work
- Full JSON debug output for recent snapshots
- Deterministic tests using synthetic candles

## Safety / Non-Goals

AtlasTrader is not currently a live trading system.

Current non-goals:

- No real trade placement
- No broker integration
- No live execution
- No paper trading engine yet
- No server/watchlist runner yet
- No email, SMS, Discord, Telegram, or other notification delivery yet
- No buy/sell/short recommendations
- No promises of profitability

Early future alerts should be informational and watch-only. They should help review whether
AtlasTrader's reported reads match real charts. They should not automatically place trades
or imply financial advice.

Before any live trading is considered, the project should include paper-trading validation,
position-sizing controls, max daily/weekly loss limits, kill-switch behavior, logging,
broker disconnect handling, and other safety controls.

## Development Setup

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install the project in editable mode with development tools:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Run linting:

```bash
ruff check .
```

Format code:

```bash
ruff format .
```

Run the project entry point:

```bash
atlas-trader
```

Or:

```bash
python src/atlas_trader/main.py
```

## Disclaimer

AtlasTrader is for education, research, historical validation, and eventual paper trading.
It is not financial advice. Live trading should not be attempted until the system has been
thoroughly tested, reviewed, and validated in paper trading with strong safety controls.
