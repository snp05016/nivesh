# Next 30 Days: Automation & Structural Integrity

**Objective**: Move from manual execution to fully automated, monitored inference and training cycles.

## 1. MLOps Orchestration
- Migrate from shell script crontabs to Celery/Redis for task orchestration.
- Implement the Alpha158 Nightly Materialization Pipeline so that the `ml-engine` pre-computes feature matrices before market open rather than on-demand.

## 2. Advanced Backtesting
- Upgrade `backtest_engine.py` to perform a day-by-day simulated walk.
- Introduce fractional Kelly criterion position sizing based on `calibration.py` bucket accuracies.
- Add realistic Indian market slippage and STT (Securities Transaction Tax) penalties.

## 3. Dynamic Fusion Beta
- Rewrite `confidence_fusion.py` to use logistic regression (Log-Odds) instead of linear weighted addition.
- Fetch the trailing 30-day Brier scores for the LLM and the ML Engine, and inversely weight them in the fusion algorithm (Self-Improving Feedback Loop).
