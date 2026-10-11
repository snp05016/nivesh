# LightGBM Baseline Training Pipeline

## 1. Overview

### What

The LightGBM baseline is the first production classifier in the Nivesh ml-engine. It predicts the forward direction (up or down) of NSE equities over a configurable horizon (default: 20 trading days). The model is a binary LightGBM classifier (`objective=binary`) trained on the 158 Alpha158 features (from the Microsoft Qlib specification). Its output is P(up) over the horizon, not a return forecast.

### Why

Before this pipeline, the production prediction endpoint relied on a multi-factor heuristic (`InferenceEngine._fallback_score`) that blended ROC momentum, RSV mean-reversion, and volatility dampening. The heuristic has no learning capacity and cannot adapt to changing market regimes. The LightGBM baseline replaces it with a data-driven model that is trained, validated, and calibrated on historical NSE equity data with strict temporal separation.

### Architecture

The end-to-end pipeline follows this sequence:

```
OHLCV data (CSV/Parquet/yfinance)
  |
  v
Feature Pipeline (Alpha158 columns selected for training)
  |
  v
Walk-Forward Temporal Validation (no future leakage)
  |
  v
Calibrator selection (isotonic vs Platt, lower pooled Brier wins)
  |
  v
Final Model Training (all available data, median best iteration)
  |
  v
Versioned Artifact Registry (models/registry/candidate/<version>/)
  |
  v
Gated Production Deployment (promotion gate + models/MANIFEST.json)
  |
  v
Inference Endpoint (LightGBM P(up); a direction only for a gated model, else no_edge)
```

Key source files:

| File | Role |
|------|------|
| `training/train_alpha158.py` | CLI entry point (the only supported trainer), orchestrates the full pipeline |
| `training/dataset_builder.py` | Data loading and validation (CSV, Parquet, yfinance, synthetic) |
| `training/feature_pipeline.py` | Builds the feature matrix (Alpha158, extras, optional sector one-hot) and targets |
| `training/validation.py` | Temporal split generation and per-fold training/evaluation |
| `training/metrics.py` | Aggregate fold metrics and the markdown training report |
| `training/calibration.py` | Calibration report (buckets, ECE, MCE), isotonic and Platt calibrators |
| `training/model_registry.py` | Versioned artifact storage and production deployment |
| `training/provenance.py` | Git SHA, library versions and data sha256 for run metadata (ML-19) |
| `pipeline/inference.py` | Production inference (booster P(up); no_edge unless the model passed the gate) |
| `models/lgb_model.py` | LGBEnsembleModel wrapper around LightGBM Booster |
| `models/model_loader.py` | Unified loader for LightGBM, TRA, and scaler artifacts |
| `config.py` | Feature list, model paths, LightGBM hyperparameters |

---

## 2. Expected Data Schema

### Required Columns

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | string | NSE ticker symbol (e.g., `RELIANCE`, `TCS`, `INFY`) |
| `date` | date | Trading date in `YYYY-MM-DD` format |
| `open` | float | Opening price |
| `high` | float | Intraday high |
| `low` | float | Intraday low |
| `close` | float | Closing price |
| `volume` | int/float | Shares traded |

### Optional Columns

| Column | Type | Description |
|--------|------|-------------|
| `vwap` | float | Volume-weighted average price (used by some Alpha158 features) |
| `sector` | string | Sector classification (triggers one-hot encoding if present) |

### Data Requirements

- **Minimum rows per symbol:** 121 (120 days of history + 1 computable row). In practice, 500+ rows per symbol spanning 3+ years is strongly recommended for meaningful walk-forward validation.
- **Date format:** `YYYY-MM-DD`. Both CSV (parsed via `pd.read_csv(parse_dates=["date"])`) and Parquet (native datetime) are accepted.
- **Column names:** Case-sensitive. Must be lowercase (`symbol`, not `Symbol`).
- **Missing values:** Rows with NaN in any required OHLCV column are dropped during validation. Rows where no forward target can be computed (fewer than 20 trading days remaining) are excluded from training.

### Example

```
symbol,date,open,high,low,close,volume
RELIANCE,2021-01-04,1987.00,2010.50,1980.00,2005.30,12345678
RELIANCE,2021-01-05,2006.00,2025.75,1998.50,2018.40,9876543
TCS,2021-01-04,3105.00,3142.00,3090.00,3128.50,4567890
```

---

## 3. How to Run Training

All commands are run from the `ml-engine/` directory.

### Basic training with a local data file

```bash
python -m training.train_alpha158 --data-path data/nse_ohlcv.csv
```

### Training with a specific target horizon and deployment

```bash
python -m training.train_alpha158 \
    --data-path data/nse_ohlcv.csv \
    --target direction_60d \
    --deploy
```

`--deploy` is gated: a model reaches production only after it passes the promotion gate (audit item ML-05) and is registered with a verified `models/MANIFEST.json` (audit item ML-07). See section 5.

### Training with data fetched from yfinance (NIFTY 50)

The dataset builder can fetch NIFTY 50 constituent history directly. Use the `fetch_nifty50()` function in `training/dataset_builder.py` to produce a Parquet file, then pass it to the training script:

```python
from training.dataset_builder import fetch_nifty50
df = fetch_nifty50(start_date="2019-01-01")
df.to_parquet("data/nse_ohlcv.parquet", index=False)
```

Then:

```bash
python -m training.train_alpha158 --data-path data/nse_ohlcv.parquet
```

yfinance prices are fetched with `auto_adjust=True`, so history changes after every corporate action, and `*.csv` / `*.parquet` are git-ignored. For each released model, archive the exact training file in versioned storage with its `provenance.dataframe_sha256(df)` and record the hash in the artifact metadata (ML-19).

### Custom walk-forward folds

```bash
python -m training.train_alpha158 \
    --data-path data/nse_ohlcv.csv \
    --folds "2021:2022,2022:2023,2023:2024"
```

### CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--data-path` | `data/ohlcv.parquet` | Path to OHLCV CSV or Parquet file |
| `--target` | `direction_20d` | Target column name. Available: `direction_20d`, `direction_60d` |
| `--folds` | `2021:2022,2022:2023,2023:2024,2024:2025` | Walk-forward folds as `train_end:val_year` pairs |
| `--deploy` | `false` | Deploy the trained model after training (gated, see section 5) |
| `--min-train-samples` | `500` | Minimum samples required per fold (train and val) |

---

## 4. How to Inspect Metrics

After a training run completes, all artifacts are saved to a versioned directory under `models/registry/candidate/`.

### Per-fold validation results

```
models/registry/candidate/<version>/validation_metrics.json
```

Contains a JSON array of per-fold result dictionaries. Each entry includes: `fold_id`, `train_end_year`, `val_year`, `hit_rate`, `precision`, `recall`, `roc_auc`, `brier_score`, `avg_return_when_bullish`, `avg_return_when_bearish`, `calibration_by_bucket`, `feature_importance`, `n_train`, `n_val`, `best_iteration`.

### Calibration report

```
models/registry/candidate/<version>/calibration_report.json
```

Contains probability calibration analysis of the pooled walk-forward predictions after the selected calibrator, with four buckets (`[0.0, 0.3)`, `[0.3, 0.5)`, `[0.5, 0.7)`, `[0.7, 1.0]`), plus ECE (Expected Calibration Error), MCE (Maximum Calibration Error), `best_method` (`isotonic` or `platt`, whichever has the lower Brier score) and that method's `brier_score`. The fitted calibrator is saved next to it as `calibrator.joblib`.

### Feature importance and training metadata

```
models/registry/candidate/<version>/metadata.json
```

Contains: `model_version`, `target`, `folds`, `n_folds_completed`, `n_features`, `n_total_samples`, `final_num_boost_round`, `lightgbm_params`, `data_date_range`, `n_symbols`, `num_trees`, `saved_at`.

Feature importance is embedded in `validation_metrics.json` per fold as a ranked list of `(feature_name, importance)` tuples sorted descending.

### Training report (console)

The pipeline prints a formatted markdown report (`metrics.generate_training_report`) to stdout at the end of training (Step 10). This report includes: training configuration, dataset summary, per-fold results table, aggregate metrics, calibration analysis, top 20 features, and automated recommendations (e.g., warnings if hit rate < 52%, ROC AUC < 0.55, or ECE > 0.05).

### Feature list

```
models/registry/candidate/<version>/features.json
```

Ordered JSON array of all feature column names used during training.

---

## 5. Model Version System

### Version Format

```
lightgbm_alpha158_candidate_v1_YYYYMMDD
```

Example: `lightgbm_alpha158_candidate_v1_20260624`

The version string encodes: model family (`lightgbm`), feature set (`alpha158`), registry status at save time (`candidate`), schema version (`v1`), and UTC training date. The date-only suffix means two runs on the same day share a version; ML-07 makes versions unique and artifacts immutable.

### Artifact Directory Structure

```
models/registry/candidate/
  lightgbm_alpha158_candidate_v1_20260624/
    model.txt                  # LightGBM Booster in text format (objective=binary)
    features.json              # Ordered feature column names
    metadata.json              # Training params, data stats, hyperparams
    validation_metrics.json    # Per-fold walk-forward results
    calibration_report.json    # Probability calibration analysis
    calibrator.joblib          # Selected isotonic or Platt calibrator
    VERSION                    # Plain text file with version string
```

### Deployment

Deployment is gated. `--deploy` (or `deploy_to_production()`) must first pass the promotion gate (audit item ML-05): Brier skill score against the training base rate with a confidence interval above 0, AUC lower bound above 0.52 per fold, no single predicted class above 80%, net-of-cost lift over always-up and momentum, and an independent holdout. A failed gate stops the deploy before anything is copied; there is no override.

A model that passes is copied to `models/lgb_model.txt` together with `models/MANIFEST.json` (audit item ML-07), which records the model version, the sha256 of the model file, objective, feature list, git SHA, data sha256, the gate result, `base_rate` and `neutral_band`. `ml-engine` verifies the manifest at startup and serves `no_edge` for any booster without one whose gate passed (section 6). Do not copy a model into `models/` by hand.

### Listing and Loading Versions

```python
from training.model_registry import list_model_versions, load_model_artifact

# List all trained versions (sorted ascending by date)
versions = list_model_versions("candidate")

# Load the latest artifact
artifact = load_model_artifact()  # latest stable, else latest candidate; {"model": Booster, "features": [...], "metadata": {...}}

# Load a specific version
artifact = load_model_artifact("lightgbm_alpha158_candidate_v1_20260624", status="candidate")
```

---

## 6. Production Endpoint Behavior

The `InferenceEngine` in `pipeline/inference.py` serves the booster's output as a probability. It never turns an unvalidated model, or a heuristic, into a direction.

### Trained Model Mode

When `models/lgb_model.txt` exists and loads successfully:

- The booster must be a binary classifier (`objective=binary`). Startup fails otherwise, because the output is read as P(up) over the 20-day horizon, not as a return forecast.
- The booster receives a single-row Alpha158 feature vector. Its output is returned as `p_up` (and `raw_score`). It is never compared with return-scale thresholds.
- A direction is served only when `models/MANIFEST.json` records a passed promotion gate (`"gate": {"passed": true}`) together with the training `base_rate` (share of up labels) and a `neutral_band` chosen on held-out data. Then, with `edge = p_up - base_rate`:
  - `expected_direction` is `+1` if `edge > neutral_band`, `-1` if `edge < -neutral_band`, `0` otherwise;
  - `confidence_score = 0.5 + |edge|`, capped at `max_confidence` (0.5 means no edge over the base rate);
  - `signal_state = "ok"`.
- Without such a manifest, every response is `signal_state = "no_edge"` with `expected_direction = 0` and `confidence_score = 0.0`. The backend then reports "no validated signal" and the iOS app hides the direction and confidence. This is the current state: the shipped 3-tree booster outputs 0.52-0.63 for any input, so a 0.5 cut-off would label every stock bullish (the training up-rate is about 0.58).
- Response metadata: `ml_engine_mode = "trained_lightgbm_baseline"`, plus `model_validated` (gate passed) and `base_rate` from the manifest.

### No Model, TRA and Ensemble

When no trained model file exists, or `model_type` is `tra` or `ensemble` (no TRA weights ship), the response is `signal_state = "no_edge"` with `p_up = null`. No heuristic direction is produced.

### Response Shape

All modes return the same dict structure:

```json
{
  "expected_direction": 0,
  "confidence_score": 0.0,
  "raw_score": 0.579334,
  "p_up": 0.579334,
  "base_rate": null,
  "signal_state": "no_edge",
  "features_used": ["KMID", "KLEN", "KMID2", "..."]
}
```

`/predict/single` and `/predict/cross-section` add `model_validated`, `ml_engine_mode`, `lightgbm_loaded`, `horizon` and `model_version`. The `model_version` field is populated from `models/DEPLOYED_VERSION` when a trained model is active, allowing downstream consumers to track which model produced each prediction.

---

## 7. Features

### Alpha158 Features (158 total)

The feature set follows the Microsoft Qlib Alpha158 specification. Features are computed by `pipeline/feature_computer.py` (FeatureComputer) using 5 rolling windows: 5, 10, 20, 30, and 60 trading days.

| Category | Count | Prefixes | Description |
|----------|-------|----------|-------------|
| Kline Basic | 9 | KMID, KLEN, KMID2, KUP, KUP2, KLOW, KLOW2, KSFT, KSFT2 | Candlestick geometry ratios |
| Static Price | 4 | OPEN0, HIGH0, LOW0, VWAP0 | Single-day price ratios to close |
| Trend | 25 | ROC, MA, BETA, RSQR, RESI | Rolling momentum and regression |
| Volatility | 30 | STD, MAX, MIN, QTLU, QTLD, RSV | Rolling dispersion and quantiles |
| Extreme Position | 15 | IMAX, IMIN, IMXD | Day-of-max/min within window |
| Price-Volume Stats | 45 | CORR, CORD, CNTP, CNTN, CNTD, SUMP, SUMN, SUMD, RANK | Directional counting and correlation |
| Volume Volatility | 10 | VMA, VSTD | Volume moving average and std |
| Price-Volume Weighted | 20 | WVMA, VSUMP, VSUMN, VSUMD | Volume-weighted directional moves |

### Extra Features (8 total, not used for training)

Computed directly from raw OHLCV arrays in `training/feature_pipeline.py`. They are present in the feature matrix, but `train_alpha158` trains on the Alpha158 columns only, because inference computes only those:

| Feature | Computation |
|---------|-------------|
| `momentum_20d` | `(close[t] - close[t-20]) / close[t-20]` |
| `momentum_60d` | `(close[t] - close[t-60]) / close[t-60]` |
| `momentum_120d` | `(close[t] - close[t-120]) / close[t-120]` |
| `volatility_20d` | Standard deviation of daily returns over 20 days |
| `volatility_60d` | Standard deviation of daily returns over 60 days |
| `volume_trend_20d` | `volume[t] / mean(volume[t-20:t])` |
| `drawdown_20d` | `(close[t] - max(close[t-20:t])) / max(close[t-20:t])` |
| `rsi_14` | Standard Wilder RSI over 14-day returns |

### Sector One-Hot Encoding

If the input data contains a `sector` column, the feature pipeline produces binary indicator columns (e.g., `sector_Energy`, `sector_IT`) encoded as `int8` for LightGBM compatibility. Missing sectors default to `"Unknown"`. Like the extra features, they are not used for training.

### Target Columns

The feature pipeline computes four targets from future price data (strictly after date T):

| Column | Definition |
|--------|------------|
| `forward_return_20d` | `(close[t+20] - close[t]) / close[t]` |
| `forward_return_60d` | `(close[t+60] - close[t]) / close[t]` |
| `direction_20d` | `1` if `forward_return_20d > 0`, else `0` |
| `direction_60d` | `1` if `forward_return_60d > 0`, else `0` |

---

## 8. Walk-Forward Validation

### Why Walk-Forward

Standard random train/test splits are invalid for financial time series. A model trained on 2023 data and tested on 2021 data has future information leakage. Walk-forward validation enforces strict temporal causality: every training set contains only data from before the validation period.

### Split Logic

For each fold `(train_end_year, val_year)`:

- **Training set:** All rows where `date.year <= train_end_year`
- **Validation set:** All rows where `date.year == val_year`

This means training sets are cumulative (expanding window). Each fold adds one more year of data to training.

### Default Folds

| Fold | Training Data | Validation Year |
|------|---------------|-----------------|
| 0 | All data up to 2021 | 2022 |
| 1 | All data up to 2022 | 2023 |
| 2 | All data up to 2023 | 2024 |
| 3 | All data up to 2024 | 2025 |

Folds with fewer than `min_train_samples` (default: 500) rows in either the training or validation set are automatically skipped with a warning.

### Metrics Per Fold

Each fold reports:

| Metric | Description |
|--------|-------------|
| **Hit Rate** | Fraction of correct direction predictions (`accuracy`) |
| **Precision** | `TP / (TP + FP)` for bullish predictions |
| **Recall** | `TP / (TP + FN)` for bullish predictions |
| **ROC AUC** | Area under the receiver operating characteristic curve |
| **Brier Score** | Mean squared error of predicted probabilities vs. actuals |
| **Avg Return When Bullish** | Mean forward return for samples predicted as bullish |
| **Avg Return When Bearish** | Mean forward return for samples predicted as bearish |
| **Calibration by Bucket** | Actual hit rate vs. predicted probability per bucket |
| **Feature Importance** | LightGBM split-based importance, ranked descending |
| **Best Iteration** | Early stopping iteration (used to set final model rounds) |

### Final Model Training

After walk-forward validation completes, a final model is trained on all available data. The number of boosting rounds is set to the **median best iteration** across folds (from early stopping), preventing overfitting while capturing the typical optimal complexity.

---

## 9. Known Limitations

- **No market regime routing.** The model uses a single set of parameters across all market conditions (bull, bear, sideways). Performance may degrade during regime transitions. This is planned for TRA integration (see section 10).

- **No intraday data.** Features are computed from daily OHLCV bars only. Intraday price patterns, order flow, and microstructure signals are not captured.

- **Survivorship bias.** If the training universe is based on current index constituents (e.g., NIFTY 50 as of 2024), stocks that were delisted or removed from the index before the training period are excluded. This inflates historical performance estimates.

- **Calibration quality depends on sample size.** Probability calibration (ECE, bucket accuracy) is computed from pooled walk-forward validation predictions. With small universes or short histories, bucket counts may be too low for reliable calibration.

- **yfinance rate limits.** Fetching 50 symbols with 5+ years of history requires sequential API calls with rate limiting (0.5s sleep per symbol). Total fetch time for NIFTY 50 is approximately 30 seconds. Larger universes may trigger Yahoo Finance throttling.

- **Alpha158 window warmup.** The first 120 rows per symbol are consumed as warmup for the longest rolling windows (60-day Alpha158 and 120-day momentum). Symbols with fewer than 121 rows are skipped entirely.

- **Binary classification only.** The model predicts up/down direction. Magnitude of expected return is not modeled (though `forward_return_20d`/`forward_return_60d` are available as continuous targets for future regression models).

- **No transaction cost modeling.** Hit rate and return metrics do not account for brokerage, STT, slippage, or impact costs. A 52% hit rate may not be profitable after costs on low-conviction signals.

---

## 10. Next Steps Toward TRA Regime Routing

The current pipeline is designed as the foundation for a regime-aware prediction system. The planned evolution path:

### Step 1: Analyze Walk-Forward Results by Regime

Use the per-fold validation metrics to identify performance variation across market regimes. If hit rate drops significantly in specific years (e.g., 2022 bear market), this confirms the need for regime-conditional models.

### Step 2: Train Separate Models per Regime

Partition the training data into regime buckets (bull, bear, sideways) using realized volatility, drawdown depth, or index-level trend indicators. Train independent LightGBM classifiers per regime and evaluate whether per-regime models outperform the single baseline.

### Step 3: TRA PyTorch Model for Regime Detection

The TRA (Temporal Routing Adapter) model in `pipeline/tra_sequence.py` is a sequence model that processes `[batch, seq_len=60, features=158]` tensors. It uses learned routing weights to assign each prediction to one of `num_states` regimes. Once trained, TRA provides a soft regime assignment that can route inference to the appropriate LightGBM specialist model.

### Step 4: TimesFM Integration for Sequential Modeling

Integrate Google TimesFM or a similar foundation model for time-series forecasting. TimesFM can provide a complementary sequential prediction signal that captures longer-range temporal dependencies not available to the tabular LightGBM model. The ensemble weights (currently 60% LightGBM / 40% TRA in `InferenceEngine`) would be extended to incorporate the TimesFM signal.

### Target Architecture

```
OHLCV input
  |
  v
Feature Computer (Alpha158)
  |
  +--> TRA Regime Detector --> regime_id
  |
  +--> LightGBM[regime_0] --+
  +--> LightGBM[regime_1] --+--> Weighted Ensemble --> final prediction
  +--> LightGBM[regime_2] --+
  +--> TimesFM sequential  --+
```

The walk-forward validation framework already supports this architecture. The `model_factory` callable in `run_walk_forward()` can be replaced with a regime-routing wrapper without changes to the evaluation or registry code.
