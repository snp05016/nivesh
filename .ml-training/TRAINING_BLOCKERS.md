# Training Blockers

Before full-scale LightGBM training can proceed in Phase 3, these blockers must be resolved:

1. **Corporate Action Adjustment**:
   Raw OHLCV data must be split-adjusted before entering `feature_builder.py`. Without this, forward targets (`closes[i+20] / closes[i]`) will be catastrophically wrong.

2. **Embargo Window in Walk-Forward**:
   `walk_forward.py` must drop the last 20 trading days of the training set before evaluating the validation year to prevent target bleed across the split boundary.

3. **Missing `dataset_builder.py`**:
   We need an executable script that bridges the database/bhavcopy to `feature_builder.py` and outputs the final `.parquet` feature matrix.

4. **Multi-class LightGBM vs Binary**:
   `train_lightgbm_baseline.py` must align exactly with the prediction threshold (`0.005`) used in `inference.py`. Currently, `inference.py` classifies `[-1, 0, 1]`, while training evaluates binary `[0, 1]`.
