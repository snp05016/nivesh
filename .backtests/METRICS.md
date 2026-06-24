# Backtest Metrics Definition

The `BacktestEngine` calculates the following key metrics for every run:

## Classification Metrics
- **Hit Rate**: The percentage of predictions where the model's predicted direction matched the actual direction.
- **Precision**: Of all the 'Buy' signals generated, what percentage actually had positive returns?
- **Recall**: Of all the true positive returns in the dataset, what percentage did the model capture?
- **Brier Score**: Measures the accuracy of probabilistic predictions. Lower is better. Essential for understanding calibration.

## Financial Metrics
- **CAGR (Compound Annual Growth Rate)**: The annualized return of the simulated portfolio, assuming daily reinvestment.
- **Sharpe Ratio**: Measures risk-adjusted return (excess return over the risk-free rate per unit of volatility). A Sharpe > 1.0 is considered acceptable; > 2.0 is excellent.
- **Sortino Ratio**: Similar to Sharpe, but only penalizes downside volatility. Crucial for assessing tail-risk in the model's predictions.
- **Max Drawdown**: The maximum observed loss from a peak to a trough before a new peak is attained. Indicates the "worst-case scenario" pain for an investor following the model.
- **Win Rate (Financial)**: The percentage of executed trades that resulted in a profit > 0 (differs from hit rate if confidence thresholds are applied).
