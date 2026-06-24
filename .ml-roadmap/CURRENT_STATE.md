# Current State of Nivesh ML Engine

## Subsystem Overviews
- **Feature Pipeline (`feature_pipeline.py`)**: Fully modular and capable of constructing Alpha158 features, cross-sectional quantiles, and standard momentum indicators.
- **Model Training & Registry (`train_lightgbm.py`, `model_registry.py`)**: Supports rigorous walk-forward cross-validation. The model registry allows saving LightGBM artifacts with status tagging (`latest`, `stable`, `candidate`, `deprecated`) to `models/registry/`.
- **Validation & Metrics (`validation.py`, `metrics.py`, `calibration.py`)**: Fully decoupled from the training script. Implements strict temporal embargoing and produces granular classification and probabilistic calibration (ECE/MCE) metrics.
- **Backtesting (`backtest_engine.py`)**: New engine capable of calculating standard quantitative financial metrics (CAGR, Sharpe, Max Drawdown) from temporal validation folds.
- **Decision Fusion (`confidence_fusion.py`)**: Consolidates predictions across LLM and Quant models. Currently, it linearly scales probabilities and overweights the LLM over the ML output.
