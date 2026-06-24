# Implementation Priority

Based on the audit, the transition to a production-grade quant platform requires addressing the following in order:

### Priority 1: Training Integrity (Phase 2 & 3)
Ensure the LightGBM training pipeline is mathematically sound. Remove survivorship bias, enforce walk-forward validation strictly, and structure the pipeline into modular `dataset_builder.py`, `feature_pipeline.py`, and `train_lightgbm.py`.

### Priority 2: Calibration Feedback Loop (Phase 6)
Audit the confidence fusion system. We must adapt the weights based on the empirical calibration data gathered by the backend.

### Priority 3: Model Governance (Phase 4)
Implement the `models/registry/` structure to support `latest`, `stable`, `candidate`, and `deprecated`. Never overwrite existing models.

### Priority 4: Backtesting Framework (Phase 5)
Implement a robust portfolio-level backtester that computes Max Drawdown, Sharpe, and CAGR to prove the model's economic viability before trusting it.

### Priority 5: Testing & Automation (Phase 8)
Write unit tests for the ML boundaries (feature generation, model loading, missing data handling) to prevent silent regressions.
