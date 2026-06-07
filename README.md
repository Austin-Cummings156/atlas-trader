# AtlasTrader

AtlasTrader is a Python market analysis and trading research system focused first on swing and position trading, not day trading.

The project starts as a market reader, not an automated trading bot. The first goal is to understand price action, trend structure, volume behavior, higher-timeframe context, and eventually fundamental data before any trade execution is considered.

The initial trading focus is intentionally slower and more forgiving. Swing and position trading should require less constant screen-watching than day trading, while still building chart-reading logic that may later be useful for shorter-term systems.

## Project Goals

AtlasTrader is intended to grow through several stages:

1. Read and classify market candles.
2. Detect trends, ranges, congestion, and consolidation.
3. Identify support, resistance, and important price zones.
4. Analyze volume in context.
5. Compare multiple timeframes such as 4H, 1D, and long-term yearly context.
6. Add fundamental analysis for swing and position trading.
7. Backtest systems using historical data.
8. Paper trade before any live trading.
9. Add alerts, reporting, and safety systems.
10. Eventually research live automation only after the system proves itself.

## Version Roadmap

- v0.1 — Project setup
- v0.2 — Candle reader
- v0.3 — Trend, range, and consolidation detection
- v0.4 — Support, resistance, and volume context
- v0.5 — Multi-timeframe analysis
- v0.6 — Fundamentals reader
- v0.7 — Historical backtesting
- v0.8 — Paper trading
- v0.9 — Alerting and safety systems
- v1.0 — Complete swing/position research bot

## First Trading Focus

The first trading mode will focus on swing and position trading. Day trading is not the initial target.

This means AtlasTrader will eventually look for trades that may last from several days to several months, usually with the goal of following larger market trends instead of reacting to short-term noise.

The same candle, trend, range, support, resistance, and volume logic may eventually help with day-trading research, but that comes later. The first priority is building a system around more forgiving setups that do not require constant monitoring.

Initial timeframes of interest:

- 4H candles for recent structure and possible entry timing
- 1D candles for primary trend direction
- Long-term yearly context for major trend and key levels

## Planned System Areas

### Market Reading

- Candle direction
- Candle body size
- Upper and lower wick size
- Strong candles
- Weak candles
- Indecision candles
- Candle comparisons

### Market Structure

- Uptrends
- Downtrends
- Sideways markets
- Trading ranges
- Congestion
- Consolidation
- Swing highs
- Swing lows
- Higher highs and higher lows
- Lower highs and lower lows

### Key Levels

- Support
- Resistance
- Breakouts
- Failed breakouts
- Retests

### Volume

- Rising volume
- Falling volume
- Breakout volume
- Weak volume moves
- Exhaustion behavior

### Fundamentals

Planned future fundamental checks may include:

- Annual growth rate
- Five-year performance
- One-year performance
- Quarterly earnings records
- P/E ratio
- EPS growth
- Revenue growth
- Debt levels
- Profitability metrics

### Backtesting

AtlasTrader will eventually support testing strategies over historical data.

The goal is to track:

- Profit and loss
- Win rate
- Average winner
- Average loser
- Maximum drawdown
- Fees
- Slippage
- Strategy metadata
- Trade system name
- Entry reason
- Exit reason

### Alerts and Safety

Future alerting may include:

- Daily reports
- Trade entry alerts
- Trade exit alerts
- Broker connection warnings
- Data feed warnings
- Server shutdown warnings
- Hard stop alerts
- Trading halt alerts

## Current Status

Version: 0.7.0 in progress

Current focus:

- Historical market-reading validation before paper trading
- Rolling-window reads over historical candles
- Trend, range, support/resistance, volume, breakout, and bias summaries
- Deterministic synthetic tests for reader behavior
- Optional real-symbol historical read-through script

### v0.2 Candle Reader

The candle reader provides tested building blocks for later chart structure work.

Current candle analysis supports:

- OHLCV candle validation
- Candle direction
- Candle body, range, and wick measurements
- Candle strength classification
- Strong bullish and strong bearish candle classification
- Indecision candle classification
- Long upper and lower wick detection
- Close position classification: near high, mid-range, or near low
- Batch candle analysis
- Previous-candle comparisons
- Inside bar and outside bar detection
- Rolling range context: wide, average, narrow, or unknown

### v0.3 Trend, Range, and Consolidation Detection

The v0.3 reader adds tested structure detection on top of the candle reader.

Current structure analysis supports:

- Confirmed swing high and swing low detection
- Uptrend detection from higher highs and higher lows
- Downtrend detection from lower highs and lower lows
- Sideways classification for mixed or weak swing structure
- Trading range detection from repeated support and resistance touches
- Congestion detection for tight overlapping sideways price action
- Consolidation detection for bounded sideways pauses
- Prior-window breakout direction checks
- Immutable candle, trend, and range settings objects for tuning analysis thresholds

### v0.4 Support, Resistance, and Volume Context

The v0.4 reader adds level detection and volume context for judging price action around
important zones.

Current support/resistance and volume analysis supports:

- Support and resistance detection from clustered swing lows and highs
- Nearest support and nearest resistance lookup around the latest close
- Level touch counts, price zones, distance from close, and confidence scores
- Simple moving average helpers for close-price context
- Rolling volume average
- Relative volume classification: high, average, low, or unknown
- Volume trend classification: rising, falling, flat, mixed, or unknown
- Breakout volume context: confirmed, weak, absent, or unknown

### v0.5 Multi-Timeframe Analysis

The v0.5 reader starts combining the existing market-reading modules across multiple
timeframes for swing and position context.

Current multi-timeframe analysis supports:

- Individual timeframe summaries that compose trend, sideways/range, support/resistance,
  and volume analysis
- Timeframe roles for recent, primary, long-term, and supporting context
- Default swing/position roles for 4H, 1D, and 1Y candles
- Directional bias classification: bullish, bearish, sideways, or unknown
- Cross-timeframe alignment classification: strong bullish, bullish, strong bearish,
  bearish, sideways, conflicted, or unknown
- Weighted confidence that gives higher-timeframe context more influence by default
- Directional conflict reporting when analyzed timeframes disagree

### v0.6 Fundamentals Reader

The v0.6 reader adds a data-only fundamentals analysis layer for swing and position
research. It classifies supplied company metrics without fetching live external data.

Current fundamental analysis supports:

- Raw fundamental metric validation for one symbol
- Growth context from annual growth, EPS growth, and revenue growth
- Performance context from one-year and five-year performance
- Quarterly EPS trend classification: improving, flat, declining, mixed, or unknown
- P/E valuation context: low, fair, high, or unknown
- Debt load classification from debt-to-equity ratio
- Profitability classification from profit margin and return on equity
- Overall score, data-quality ratio, and rating: strong, positive, neutral, weak,
  or unknown
- Immutable settings object for tuning fundamental thresholds

### v0.7 Historical Market-Reading Validation

The in-progress v0.7 reader starts historical testing as market-reading validation, not full
profit/loss backtesting. It walks historical candles chronologically and runs the
current readers over rolling windows to check whether AtlasTrader can describe market
structure coherently before paper trading is added.

Current historical validation supports:

- Rolling historical snapshots over a configurable candle lookback
- Per-snapshot trend, sideways/range, support/resistance, volume, breakout, and bias reads
- Summary counts for trend direction, market type, breakout direction, and bias
- High-relative-volume and confirmed-breakout-volume counts
- Deterministic tests using synthetic candles
- Optional real-data script:

```bash
python scripts/run_historical_read.py --symbol AAPL --period 2y --interval 1d
```

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

Run the project:

```bash
atlas-trader
```

Or:

```bash
python src/atlas_trader/main.py
```

## Disclaimer

AtlasTrader is for education, research, backtesting, and paper trading. It is not financial advice. Live trading should not be attempted until the system has been thoroughly tested, reviewed, and proven in paper trading.
