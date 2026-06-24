# training/

LightGBM direction-prediction pipeline with walk-forward temporal validation. No future leakage by construction.

## Structure

| File | Purpose |
|------|---------|
| `train_lightgbm_baseline.py` | Main training entrypoint. Loads data, builds features, runs walk-forward CV, trains final model, saves artifact. |
| `feature_builder.py` | Alpha158 features (via `pipeline.feature_computer`) + 8 extra momentum/volatility/volume features + forward-return target generation. |
| `walk_forward.py` | Temporal cross-validation. Each fold trains on strictly past data and validates on a future year. No random splits. |
| `model_registry.py` | Versioned artifact storage under `artifacts/`. Handles save, load, and deploy-to-production. |
| `evaluation.py` | Aggregates fold results, calibration analysis (bucketed confidence vs. accuracy), formatted training reports. |
| `data_adapter.py` | Loads OHLCV data from CSV, Parquet, yfinance (single symbol or NIFTY 50 batch), or synthetic random-walk for testing. |
| `artifacts/` | Trained model storage. Each version gets its own directory with model file, feature list, metadata, and metrics. Gitignored. |

## Quick Start

```bash
# 1. Train with walk-forward validation on a CSV/Parquet file
python -m training.train_lightgbm_baseline --data-path /path/to/ohlcv.csv

# 2. Train with a specific target (default: direction_20d)
python -m training.train_lightgbm_baseline --data-path /path/to/ohlcv.parquet --target direction_60d

# 3. Train and deploy the final model to production path
python -m training.train_lightgbm_baseline --data-path /path/to/ohlcv.csv --deploy
```

Run from the `ml-engine/` directory so module imports resolve correctly.

## Data

### Expected Format

Any CSV or Parquet file with these required columns:

```
symbol | date | open | high | low | close | volume
```

- `date` is parsed automatically (any standard format).
- Rows must be sorted by `(symbol, date)`.
- Multiple symbols in a single file are supported.

### Sources

- **Local file:** Pass `--data-path` pointing to a CSV or Parquet.
- **yfinance:** `data_adapter.fetch_from_yfinance("RELIANCE.NS")` or `fetch_nifty50()` for bulk NIFTY 50 history (default start: 2019-01-01).
- **Synthetic:** `data_adapter` can generate random-walk data for testing without network access.

## Artifacts

Each training run saves a versioned directory under `training/artifacts/`:

```
artifacts/
  lgb_v20260624_143012/
    model.txt          # LightGBM booster in text format
    features.json      # Ordered feature list used at training time
    metadata.json      # Training config, data stats, timestamps
    metrics.json       # Walk-forward fold results and aggregated scores
    calibration.json   # Confidence-bucket calibration report
```

### Inspect a saved model

```python
from training.model_registry import load_model_artifact

artifact = load_model_artifact()           # loads latest version
artifact = load_model_artifact("lgb_v...") # loads specific version
```

### Deploy to production

`deploy_to_production(model_version)` copies the model and feature list to:

- `ml-engine/models/lgb_model.txt`
- `ml-engine/models/features.json`
- `ml-engine/models/DEPLOYED_VERSION` (version marker)

The `--deploy` flag in the training script calls this automatically after a successful run.
