# AtlasTrader

AtlasTrader is a Python market analysis and trading research system focused first on swing and position trading.

The project starts as a market reader, not an automated trading bot. The first goal is to understand price action, trend structure, volume behavior, higher-timeframe context, and eventually fundamental data before any trade execution is considered.

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

The first trading mode will focus on swing and position trading.

This means AtlasTrader will eventually look for trades that may last from several days to several months, usually with the goal of following larger market trends instead of reacting to short-term noise.

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

Version: 0.3.0

Current focus:

- Trend detection
- Swing high and swing low detection
- Trading range detection
- Consolidation detection
- Congestion detection

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
