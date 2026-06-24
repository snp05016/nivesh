# Backtest Report

## Overview
This report outlines the capabilities and integration of the newly built Quantitative Backtest Engine (`ml-engine/training/backtest_engine.py`) within the Nivesh ML platform. 

The engine allows Nivesh to simulate historical portfolio performance over cross-sectional predictions, answering the critical question: *If we traded every prediction the ML model made over the validation period, what would the portfolio returns look like?*

## Architecture Integration
1. **Source**: The `BacktestEngine` consumes prediction dictionaries produced during walk-forward validation (`validation.py`).
2. **Inputs**: `y_prob` (model confidence), `y_true` (binary direction), and `forward_return` (actual day-n return).
3. **Outputs**: Computes standard ML classification metrics (Hit Rate, Precision, Recall, Brier Score) and translates them into quantitative finance metrics (CAGR, Sharpe Ratio, Sortino Ratio, Max Drawdown).

## Next Steps for Production Execution
Currently, the backtest engine is a standalone module. To fully realize its potential:
- It must be integrated into `metrics.py` so that every `run_walk_forward` fold automatically produces an equity curve and Sharpe ratio.
- We need to ensure that `forward_return` is accurately tracked and passed alongside `y_true` during validation evaluation.
- Transaction costs (`transaction_cost=0.001` default) should be calibrated against Nivesh's actual assumed slippage and brokerage models.
