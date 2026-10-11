# Nivesh Production Readiness Scorecard

Based on the multi-phase audit of the Nivesh prediction and ML infrastructure, the system has been evaluated across 5 key dimensions of production readiness for a self-improving quantitative platform.

## Overall Score: 68 / 100
**Status:** In Transition (Analytics Exists → Self-Improving Platform)

---

## 1. Data Integrity & Ingestion (75 / 100)
- **Strengths**: The `dataset_builder.py` and `feature_pipeline.py` successfully construct the Alpha158 feature set and custom momentum/volatility indicators.
- **Gaps**: Forward return tracking (`LABEL_GENERATION.md`) and temporal embargoing (`LEAKAGE_ANALYSIS.md`) are currently theoretical or loosely enforced. There is a risk of look-ahead bias if the daily ingestion pipeline does not strictly snap to market close times before generating inferences.
- **Action Required**: Enforce `T+N` label generation with strict temporal cutoffs in the database.

## 2. ML Training Infrastructure (85 / 100)
- **Strengths**: Phase 3 refactored the entire training suite into a highly modular pipeline (`train_lightgbm.py`, `validation.py`, `metrics.py`, `calibration.py`). Walk-forward validation is correctly implemented.
- **Gaps**: The pipeline is still executed manually. Automated cron-based retraining with data drift detection is not yet configured.
- **Action Required**: Implement an orchestration layer (e.g., Celery/Airflow) to trigger `train_lightgbm.py` weekly, conditioned on data freshness.

## 3. Model Governance & Deployment (90 / 100)
- **Strengths**: `model_registry.py` is fully implemented. It supports stateful promotion (`candidate` → `stable`), tracks feature schemas alongside weights, and handles atomic deployments to the production endpoints.
- **Gaps**: No automated rollback mechanism if a `stable` model begins exhibiting severe performance degradation in live predictions.
- **Action Required**: Add an active monitoring daemon that drops a model to `deprecated` and falls back to heuristics if the live Brier score exceeds a safety threshold.

## 4. Backtesting & Validation (60 / 100)
- **Strengths**: `backtest_engine.py` was introduced to calculate standard classification and quantitative finance metrics.
- **Gaps**: The engine calculates flat metrics over arrays rather than performing a true day-by-day portfolio simulation with capital limits and transaction slippage.
- **Action Required**: Upgrade the backtest engine to group by date and simulate realistic portfolio constraints.

## 5. Decision Fusion & Feedback Loops (30 / 100)
- **Strengths**: Prediction outcomes are tracked, and Brier scores are calculated.
- **Gaps**: The fusion engine (`confidence_fusion.py`) heavily overweights the uncalibrated LLM (45%) while under-weighting the ML model (max 25%). Venn-Abers is incorrectly applied as an additive pillar rather than a calibrator. Most critically, the feedback loop is completely severed: the outcomes and Brier scores are *never fed back into the fusion weights*.
- **Action Required**: Radically overhaul `confidence_fusion.py`. Implement log-odds fusion and apply Venn-Abers calibration directly to the ML probabilities. Establish a feedback loop where component weights are dynamically adjusted based on trailing 30-day Brier scores.
