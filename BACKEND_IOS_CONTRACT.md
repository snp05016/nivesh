# Strategy Lab API Contract

## Request
`POST /api/v1/analysis/backtest`
(Add this to an appropriate router, e.g., `routers/analysis.py` or create a new `routers/strategy.py` and register it in `main.py`)

**JSON Body:**
```json
{
  "ticker": "RELIANCE.NS",
  "strategy_id": "rsi_oversold", 
  "years": 5
}
```

Strategy IDs:
- `rsi_oversold`
- `golden_cross`
- `low_pe_promoter`
- `momentum_roc`
- `bollinger_reversion`
- `volume_breakout`
- `macd_signal`
- `buy_and_hold`
- `dividend_capture`
- `low_volatility`

## Response
**JSON Body:**
```json
{
  "cagr": 24.5,
  "sharpe_ratio": 1.2,
  "max_drawdown": -15.4,
  "win_rate": 65.0,
  "outperformance": 8.2,
  "trades": [
    {
      "entry_date": "2021-01-15",
      "exit_date": "2021-02-10",
      "entry_price": 2100.50,
      "exit_price": 2250.75,
      "return_pct": 7.15,
      "holding_days": 26
    }
  ],
  "equity_curve": [
    {
      "date": "2021-01-01",
      "portfolio_value": 100000.0,
      "benchmark_value": 100000.0
    }
  ]
}
```

Notes for Backend:
- All values should be computed in INR.
- Include brokerage/slippage in trade simulation as per STRATEGY_LAB_PROMPT.md.
- Ensure the date formats are "YYYY-MM-DD" or ISO 8601.

Notes for iOS:
- Parse the `equity_curve` for the chart.
- Parse `trades` for the trade log table.
- Formulate the request as per above.
