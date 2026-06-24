# Missing Components

1. **Backtesting Framework**:
   The system lacks a historical portfolio backtester. While walk-forward cross-validation computes Brier score and accuracy, it cannot simulate capital allocation, Max Drawdown, or Sharpe ratio across the NSE universe.

2. **Model Registry Lifecycle Governance**:
   Currently, models are dumped into `artifacts/lgb_v...` and the newest is deployed. There is no concept of a "Staging" model or a formal promotion workflow (`Candidate` -> `Stable`).

3. **Dynamic Confidence Fusion**:
   `backend/services/confidence_fusion.py` hardcodes fusion weights. The system possesses a robust `prediction_calibration_service.py` capable of outputting empirical recommendations, but the loop to dynamically update fusion weights is disconnected.

4. **Production Training Cron/DAG**:
   Training is a manual script (`python -m training.train_lightgbm_baseline`). There is no automated retraining trigger (e.g., "Retrain when ECE > 0.10" or "Retrain monthly").

5. **Advanced Feature Engineering**:
   The features are standard Alpha158. It lacks deep macroeconomic context features, robust sector-relative normalization, and sentiment feature embedding ingestion.
