# Phase 1: Full ML Engine Audit

This document answers the 7 core questions regarding the current state of the Nivesh ML Engine (`ml-engine/` & backend ML components).

### 1. What is production-ready?
- **FastAPI ML Microservice (`main.py`)**: Runs independently on port 8001, separating Python 3.10 requirements from the Python 3.14 backend.
- **Inference Pipeline (`pipeline/inference.py`)**: Cleanly handles batch cross-section and single predictions.
- **Backend Analytics**: Prediction logging, outcome tracking, Brier score calculation, and calibration endpoints are fully integrated and actively scoring outputs.
- **LightGBM Baseline**: `train_lightgbm_baseline.py` uses walk-forward temporal cross-validation correctly to prevent lookahead bias.

### 2. What is scaffolded but unimplemented?
- **TRA (Temporal Routing Adaptor)**: Scaffolded in `models/tra.py` and `inference.py`, but there is no training pipeline for it, leaving it permanently in fallback.
- **Model Registry Governance**: A basic `model_registry.py` exists that saves versioned folders under `artifacts/`, but it lacks strict state transitions (`candidate`, `stable`, `deprecated`).
- **Backtest Framework**: The ML engine trains and scores walk-forward metrics, but lacks a holistic portfolio-level backtester that captures Sharpe, Max Drawdown, and CAGR.

### 3. What is dead code?
- **TRA Model loading structures**: Since the TRA PyTorch model is never trained or shipped, the inference pathways anticipating it are practically dead code, taking up complexity without yielding results.
- **Empty Model Wrappers**: Potential empty wrappers in `ml-engine/models/` that are bypassed by `inference.py`.

### 4. What is partially implemented?
- **Feature Pipeline (`feature_builder.py`)**: Computes Alpha158 + 8 momentum features, but is tangled inside the training scripts rather than being a modular dataset builder.
- **Confidence Calibration (`backend/services/confidence_fusion.py`)**: The fusion equations exist, but use hardcoded weights (0.45 LLM, 0.25 Quant, etc.) instead of automatically adapting to the empirical ECE/MCE outputs from the calibration system.

### 5. What is technically incorrect?
- **Fallback Confidence Heuristic (`inference._fallback_score`)**: Synthesizes a "confidence score" based on raw momentum/RSV when no LightGBM model is found. It returns an overly smooth pseudo-probability that can artificially deflate Brier scores without genuine predictive capability.
- **Fixed Direction Threshold**: `DIRECTION_THRESHOLD = 0.005` in `inference.py` assumes ±0.5% is universally applicable regardless of the asset's idiosyncratic volatility.

### 6. What is likely to fail in production?
- **NaN Handling in Inference**: `inference.py` blindly trusts `features_df[col][0]`. If `Alpha158` returns `NaN` for `ROC5` due to missing history, the fallback score might propagate `NaN` leading to a 500 server error on JSON serialization.
- **Data Shape Assumptions**: Sequence length padding for the TRA model assumes `seq_len = 60` and pads with identical rows, which destroys sequence dynamics.

### 7. What assumptions currently exist that are not validated?
- **Survivorship Bias**: The training script `train_lightgbm_baseline.py` assumes the active NIFTY 50 constitutes the historical universe, inducing massive survivorship bias.
- **Corporate Actions**: Assumes OHLCV data passed into `feature_computer.py` is perfectly split/dividend adjusted.
- **Dialectical Symmetry**: Assumes the LLM pillar's confidence is structurally comparable to the ML pillar's confidence, despite LLMs generally exhibiting severe overconfidence.
