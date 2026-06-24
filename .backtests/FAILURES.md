# Known Limitations & Potential Failures

While the `BacktestEngine` provides robust vectorized metrics, several structural assumptions could lead to failure modes if not carefully managed:

## 1. Execution Slippage
The current engine applies a static `transaction_cost` penalty. In live markets, slippage is dynamic and depends on the order book depth and the stock's liquidity. The backtest might overestimate returns for small-cap stocks.

## 2. Portfolio Sizing and Capital Allocation
The simplified backtest assumes an equal-weighted portfolio for all generated signals on a given day. If the model generates 100 signals one day and 2 signals the next, capital allocation is highly skewed. 
**Failure Risk:** The backtest could show high CAGR driven by extreme leverage on high-signal days, which is unachievable in reality.

## 3. Forward Return Leakage
If the `forward_return` array passed to the backtester is calculated using `Close[T+N] / Close[T]`, but the model's signal is generated *after* market close on T, execution can only happen at Open[T+1]. 
**Failure Risk:** Assuming execution at Close[T] creates a look-ahead bias that artificially inflates returns.

## 4. Regime Shift Insensitivity
The metrics are currently aggregated over the entire run. If the model performs exceptionally well in a bull market but catastrophically in a bear market, the overall CAGR might hide the extreme regime-specific drawdown.
