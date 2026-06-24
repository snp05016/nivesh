# LightGBM Baseline Training Pipeline

## 1. Overview

### What

The LightGBM baseline is the first production classifier in the Nivesh ml-engine. It predicts the forward direction (up or down) of NSE equities over a configurable horizon (default: 20 trading days). The model is a binary LightGBM classifier trained on 158 Alpha158 features (from the Microsoft Qlib specification) plus 8 supplementary momentum, volatility, and volume features.

### Why

Before this pipeline, the production prediction endpoint relied on a multi-factor heuristic (`InferenceEngine._fallback_score`) that blended ROC momentum, RSV mean-reversion, and volatility dampening. The heuristic has no learning capacity and cannot adapt to changing market regimes. The LightGBM baseline replaces it with a data-driven model that is trained, validated, and calibrated on historical NSE equity data with strict temporal separation.

### Architecture

The end-to-end pipeline follows this sequence:

```
OHLCV data (CSV/Parquet/yfinance)
  |
  v
Feature Builder (Alpha158 + 8 extras + sector one-hot)
  |
  v
Walk-Forward Temporal Validation (no future leakage)
  |
  v
Final Model Training (all available data, median best iteration)
  |
  v
Versioned Artifact Registry (training/artifacts/<version>/)
  |
  v
Production Deployment (models/lgb_model.txt + features.json)
  |
  v
Inference Endpoint (LightGBM probability or heuristic fallback)
```

Key source files:

| File | Role |
|------|------|
| `training/train_lightgbm_baseline.py` | CLI entry point, orchestrates the full pipeline |
| `training/feature_builder.py` | Builds Alpha158 + extra features from OHLCV data |
| `training/walk_forward.py` | Temporal split generation and per-fold training/evaluation |
| `training/evaluation.py` | Aggregate metrics, calibration analysis, report generation |
| `training/model_registry.py` | Versioned artifact storage and production deployment |
| `training/data_adapter.py` | Data loading (CSV, Parquet, yfinance, synthetic) |
| `pipeline/inference.py` | Production inference (trained model or heuristic fallback) |
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
python -m training.train_lightgbm_baseline --data-path data/nse_ohlcv.csv
```

### Training with a specific target horizon and automatic deployment

```bash
python -m training.train_lightgbm_baseline \
    --data-path data/nse_ohlcv.csv \
    --target direction_60d \
    --deploy
```

### Training with data fetched from yfinance (NIFTY 50)

The data adapter can fetch NIFTY 50 constituent history directly. Use the `fetch_nifty50()` function in `training/data_adapter.py` to produce a Parquet file, then pass it to the training script:

```python
from training.data_adapter import fetch_nifty50
df = fetch_nifty50(start_date="2019-01-01")
df.to_parquet("data/nse_ohlcv.parquet", index=False)
```

Then:

```bash
python -m training.train_lightgbm_baseline --data-path data/nse_ohlcv.parquet --deploy
```

### Custom walk-forward folds

```bash
python -m training.train_lightgbm_baseline \
    --data-path data/nse_ohlcv.csv \
    --folds "2021:2022,2022:2023,2023:2024"
```

### CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--data-path` | `data/ohlcv.parquet` | Path to OHLCV CSV or Parquet file |
| `--target` | `direction_20d` | Target column name. Available: `direction_20d`, `direction_60d` |
| `--folds` | `2021:2022,2022:2023,2023:2024,2024:2025` | Walk-forward folds as `train_end:val_year` pairs |
| `--deploy` | `false` | Copy trained model to production path after training |
| `--min-train-samples` | `500` | Minimum samples required per fold (train and val) |

---

## 4. How to Inspect Metrics

After a training run completes, all artifacts are saved to a versioned directory under `training/artifacts/`.

### Per-fold validation results

```
training/artifacts/<version>/validation_metrics.json
```

Contains a JSON array of per-fold result dictionaries. Each entry includes: `fold_id`, `train_end_year`, `val_year`, `hit_rate`, `precision`, `recall`, `roc_auc`, `brier_score`, `avg_return_when_bullish`, `avg_return_when_bearish`, `calibration_by_bucket`, `feature_importance`, `n_train`, `n_val`, `best_iteration`.

### Calibration report

```
training/artifacts/<version>/calibration_report.json
```

Contains probability calibration analysis with four buckets (`[0.0, 0.3)`, `[0.3, 0.5)`, `[0.5, 0.7)`, `[0.7, 1.0]`), plus ECE (Expected Calibration Error) and MCE (Maximum Calibration Error). Each bucket reports `count`, `actual_hit_rate`, and `avg_predicted_prob`.

### Feature importance and training metadata

```
training/artifacts/<version>/metadata.json
```

Contains: `model_version`, `target`, `folds`, `n_folds_completed`, `n_features`, `n_total_samples`, `final_num_boost_round`, `lightgbm_params`, `data_date_range`, `n_symbols`, `num_trees`, `saved_at`.

Feature importance is embedded in `validation_metrics.json` per fold as a ranked list of `(feature_name, importance)` tuples sorted descending.

### Training report (console)

The pipeline prints a formatted markdown report to stdout at the end of training (Step 10). This report includes: training configuration, dataset summary, per-fold results table, aggregate metrics, calibration analysis, top 20 features, and automated recommendations (e.g., warnings if hit rate < 52%, ROC AUC < 0.55, or ECE > 0.05).

### Feature list

```
training/artifacts/<version>/features.json
```

Ordered JSON array of all feature column names used during training.

---

## 5. Model Version System

### Version Format

```
lightgbm_baseline_alpha158_v1_YYYYMMDD
```

Example: `lightgbm_baseline_alpha158_v1_20260624`

The version string encodes: model family (`lightgbm_baseline`), feature set (`alpha158`), schema version (`v1`), and UTC training date.

### Artifact Directory Structure

```
training/artifacts/
  lightgbm_baseline_alpha158_v1_20260624/
    model.txt                  # LightGBM Booster in text format
    features.json              # Ordered feature column names
    metadata.json              # Training params, data stats, hyperparams
    validation_metrics.json    # Per-fold walk-forward results
    calibration_report.json    # Probability calibration analysis
    VERSION                    # Plain text file with version string
```

### Deployment

When `--deploy` is passed (or `deploy_to_production()` is called programmatically), the registry copies three files to the production model directory:

| Source | Destination |
|--------|-------------|
| `training/artifacts/<version>/model.txt` | `models/lgb_model.txt` |
| `training/artifacts/<version>/features.json` | `models/features.json` |
| (generated) | `models/DEPLOYED_VERSION` (plain text with version string) |

The `DEPLOYED_VERSION` file records which registry version is currently active in production.

### Listing and Loading Versions

```python
from training.model_registry import list_model_versions, load_model_artifact

# List all trained versions (sorted ascending by date)
versions = list_model_versions()

# Load the latest artifact
artifact = load_model_artifact()  # returns {"model": Booster, "features": [...], "metadata": {...}}

# Load a specific version
artifact = load_model_artifact("lightgbm_baseline_alpha158_v1_20260620")
```

---

## 6. Production Endpoint Behavior

The `InferenceEngine` in `pipeline/inference.py` handles two modes at prediction time:

### Trained Model Mode

When `models/lgb_model.txt` exists and loads successfully:

- The LightGBM Booster receives a single-row Alpha158 feature vector and outputs a probability.
- The raw probability is mapped to a discrete direction: `+1` (bullish) if probability > 0.505, `-1` (bearish) if probability < 0.495, `0` (neutral) otherwise.
- Confidence is calibrated from the model probability using signal strength, feature coverage, volatility penalty, trend agreement, and RSV extremity.
- Response metadata: `mode = "trained_lightgbm_baseline"`.

### Fallback Heuristic Mode

When no trained model file exists:

- A multi-factor heuristic blends short-term momentum (ROC5), medium-term momentum (ROC20), RSV mean-reversion, volatility dampening (STD5), and trend agreement.
- The heuristic output is clipped to `[-0.05, +0.05]` and mapped through the same direction thresholds.
- Response metadata: `mode = "fallback_technical_heuristic"`.

### Response Shape

Both modes return the same dict structure:

```json
{
  "expected_direction": 1,
  "confidence_score": 0.6234,
  "raw_score": 0.0312,
  "features_used": ["KMID", "ROC5", "STD20", "..."],
  "model_version": "lightgbm_baseline_alpha158_v1_20260624"
}
```

The `model_version` field is populated from `models/DEPLOYED_VERSION` when a trained model is active, allowing downstream consumers to track which model produced each prediction.

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

### Extra Features (8 total)

Computed directly from raw OHLCV arrays in `training/feature_builder.py`:

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

If the input data contains a `sector` column, the feature builder produces binary indicator columns (e.g., `sector_Energy`, `sector_IT`) encoded as `int8` for LightGBM compatibility. Missing sectors default to `"Unknown"`.

### Target Columns

The feature builder computes four targets from future price data (strictly after date T):

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
