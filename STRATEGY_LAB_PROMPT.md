# STRATEGY LAB — Autonomous 4-Hour Build for Antigravity CLI

Paste into Antigravity CLI. Do not ask questions. Build everything end-to-end.
Reuse existing infrastructure aggressively. Timebox: 4 hours.

---

## GOAL

Build a Strategy Lab where users backtest pre-built and custom trading strategies
against 5 years of NSE data. See CAGR, Sharpe, max drawdown, win rate. Compare
two strategies side-by-side. Fully functional iOS screen + backend endpoint.

---

## WHAT ALREADY EXISTS (REUSE — DO NOT REBUILD)

| Component | File | What it does |
|-----------|------|-------------|
| Factor Engine | services/factor_engine.py | Deterministic RSI, MACD, SMA, Bollinger, ATR, OBV — no LLM |
| OHLCV fetcher | yfinance via market.py get_stock_history | 5 years of daily data for any NSE ticker |
| Stock list | ios/.../StockDatabase.swift | 200+ NSE stocks with sectors, names, tickers |
| Theme system | ios/.../Theme.swift + BanknoteDesignSystem.swift | bullGreen, bearRed, securityGold, banknoteCard() |
| Charts | ios/.../Charts/StockCharts.swift | Swift Charts — BarMark, LineMark, AreaMark |

---

## BACKEND: 1 new file

### FILE: backend/services/strategy_engine.py

A pure computation module. No LLM calls. No API calls beyond yfinance (which is already used).

**10 pre-built strategies:**

1. RSI Oversold — Buy when RSI(14) < 30, sell when RSI(14) > 70
2. Golden Cross — Buy when SMA(50) crosses above SMA(200), sell on Death Cross
3. Low PE + Promoter — Buy when PE < sector avg AND promoter holding > 50%, sell when PE > 1.5x sector avg
4. Momentum ROC — Buy when ROC(21) > 0, sell when ROC(21) < 0 after 5 consecutive down days
5. Bollinger Mean Reversion — Buy when price touches lower band, sell when touches middle
6. Volume Breakout — Buy when volume > 2x 20-day avg AND price > SMA(50), sell on volume exhaustion
7. MACD Signal — Buy on bullish crossover, sell on bearish crossover
8. Buy & Hold — Buy on day 1, sell on last day (benchmark)
9. Dividend Capture — Buy 3 days before ex-date, sell on ex-date (uses dividend history)
10. Low Volatility — Buy when HV(21) < 15% annualized, sell when HV > 30%

**Strategy Engine API:**



**Endpoint:** 

---

## iOS: 1 new screen

### FILE: ios/StockApp/stockme/stockme/Views/StrategyLabScreen.swift

**Layout (top to bottom):**

1. **Stock picker** — searchable dropdown, loads from StockDatabase. Default: user's first watchlist stock
2. **Strategy picker** — horizontal scrollable chips. 10 strategies, each with icon + name
   - RSI: "waveform.path.ecg", Golden Cross: "point.topleft.down.curvedto.point.bottomright.up", etc.
3. **Date range** — preset chips: 1Y, 3Y, 5Y, ALL
4. **Results hero card** — after backtest runs:
   - Large CAGR number (e.g. "+24.5% CAGR") green if positive
   - Sharpe ratio, max drawdown, win rate in 3-column grid below
   - "vs Buy & Hold: +8.2% outperformance" pill
5. **Equity curve chart** — LineMark chart: blue line = strategy, grey dashed = benchmark
   - X-axis: dates, Y-axis: portfolio value in Rupees
   - Shaded area between strategy and benchmark when outperforming
6. **Trade log** — collapsed by default. Expand to show table:
   - Entry date, exit date, entry ₹, exit ₹, return %, holding days
   - Each row colored green (profit) or red (loss)
7. **Compare button** — "Compare with another strategy" → splits screen, runs second backtest
   - Same stock, different strategy. Two equity curves overlaid.

**States:**
- Loading: shimmer skeleton while backend computes
- Error: "Not enough data" / "API unavailable" with retry button
- Empty: "Select a strategy to begin"

**Design:** banknoteCard() on every card. Theme.bullGreen for profits, Theme.bearRed for losses.
IndianFormatter.price() for all Rupee values. Theme.securityGold for the Sharpe ratio (risk-adjusted is gold).

---

## VERIFICATION

1. Run backtest: RELIANCE, RSI Oversold, 5Y → should return BacktestResult with trades and equity curve
2. Compare: RELIANCE RSI vs Golden Cross → two equity curves on one chart
3. Edge case: ticker with <1yr data → graceful "insufficient data" error
4. Edge case: strategy generates 0 trades → "No trades executed" message

---

## CRITICAL RULES

- Zero LLM calls. Pure computation.
- Reuse factor_engine.py — do NOT reimplement RSI, MACD, etc.
- Account for Indian brokerage: 0.1% per trade + STT + 0.05% slippage
- All returns in INR. CAGR, P&L — never USD.
- Do NOT create a new Xcode project. Add to existing StockApp target.
- Do NOT change existing files unless adding an import or route registration.
