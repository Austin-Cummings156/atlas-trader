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

Version: 0.1.0

Current focus:

- Project setup
- Folder structure
- Development tooling
- README and GitHub initialization

## Development Setup

Create a virtual environment:

```bash
python -m venv .venv