# Proposed Engine Improvements

To upgrade the `BacktestEngine` from a basic statistical calculator to an institutional-grade simulation framework, the following improvements are prioritized:

## 1. Day-by-Day Portfolio Accounting
Instead of calculating metrics over flat arrays, the engine must group signals by `date`.
- Apply a maximum portfolio capital limit.
- Divide capital equally among the top `K` highest-confidence signals per day.
- Track cash balances, daily PnL, and cumulative equity curve dynamically.

## 2. Kelly Criterion Integration
Currently, the backtester treats all signals > 0.5 equally.
- **Improvement**: Scale the capital allocation for a specific trade based on the `y_prob` (confidence) and the model's historical calibration accuracy using a fractional Kelly sizing model.

## 3. Realistic Trade Execution Modeling
- Use `Open[T+1]` for entry rather than `Close[T]`.
- Implement dynamic slippage based on Average True Range (ATR) or historical volume.
- Implement stop-loss and take-profit bounds (e.g., exit if drawdown > 5%).

## 4. Drawdown Duration Tracking
Add metrics to track the *length* of drawdowns (Time to Recovery), not just the depth (Max Drawdown). This is critical for investor psychology and platform churn rate calculations.
