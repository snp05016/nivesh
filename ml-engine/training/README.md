# training/

LightGBM direction classifier trained with walk-forward temporal validation. There is one supported entry point, `train_alpha158.py`. The model is a binary classifier: its output is P(up) over the target horizon (default 20 trading days), never a return forecast.

## Structure

| File | Purpose |
|------|---------|
| `train_alpha158.py` | The training entry point. Loads data, builds features, runs walk-forward CV, selects a calibrator, trains the final model, saves the artifact, optionally deploys. |
| `dataset_builder.py` | OHLCV loading and validation: `load_csv`, `load_parquet`, `fetch_from_yfinance`, `fetch_nifty50`, `validate_ohlcv`, `generate_sample_csv` (synthetic random walk for tests). |
| `feature_pipeline.py` | `build_feature_matrix`: 158 Alpha158 features (via `pipeline.feature_computer`), 8 extra momentum/volatility/volume features, optional sector one-hot, and the forward-return / direction targets. `train_alpha158` uses the Alpha158 columns only. |
| `validation.py` | Walk-forward splits (`generate_splits`) and per-fold training/evaluation (`run_walk_forward`). Each fold trains on strictly earlier years and validates on a later year. No random splits. |
| `metrics.py` | `aggregate_fold_results` and the markdown `generate_training_report`. |
| `calibration.py` | `compute_calibration_report` (bucketed calibration, ECE, MCE) plus isotonic and Platt calibrators. |
| `model_registry.py` | Versioned artifacts under `models/registry/<status>/<version>/`: save, load, list, deploy. |
| `provenance.py` | Run provenance (ML-19): git SHA, library versions, `dataframe_sha256` / `file_sha256` of the training data. |

## Quick Start

Run from the `ml-engine/` directory so module imports resolve.

```bash
# Train with walk-forward validation on a CSV or Parquet file
python -m training.train_alpha158 --data-path /path/to/ohlcv.parquet

# Pick the target (default: direction_20d) and the folds (train_end:val_year pairs)
python -m training.train_alpha158 --data-path /path/to/ohlcv.csv --target direction_60d \
    --folds "2021:2022,2022:2023,2023:2024"

# Train, then deploy (gated, see below)
python -m training.train_alpha158 --data-path /path/to/ohlcv.parquet --deploy
```

Other flags: `--min-train-samples` (default 500). Without `--data-path` the script uses `data/ohlcv.parquet`.

## Data

Any CSV or Parquet file with the columns `symbol | date | open | high | low | close | volume` (optional `vwap`, `sector`). Several symbols per file are fine.

To build a NIFTY 50 file from yfinance:

```python
from training.dataset_builder import fetch_nifty50
fetch_nifty50(start_date="2019-01-01").to_parquet("data/ohlcv.parquet", index=False)
```

For tests without network access, `dataset_builder.generate_sample_csv(path, n_symbols=5, n_days=1000)` writes a synthetic random walk.

### Reproducibility: archive the data snapshot

yfinance history is fetched with `auto_adjust=True`, so past prices change whenever a corporate action happens, and `*.csv` / `*.parquet` are git-ignored. For every model that is released, archive the exact OHLCV file used for training in versioned storage together with its `provenance.dataframe_sha256(df)`, and keep that hash in the artifact metadata. Without the snapshot the model cannot be regenerated or audited.

## Artifacts

Each run saves `models/registry/candidate/<model_version>/`:

```
model.txt                 # LightGBM booster (objective=binary)
features.json             # ordered feature list used at training time
metadata.json             # target, folds, params, data date range, symbols, trees
validation_metrics.json   # per-fold walk-forward results
calibration_report.json   # buckets, ECE, MCE, selected calibrator and its Brier score
calibrator.joblib         # selected isotonic or Platt calibrator
VERSION                   # version string
```

```python
from training.model_registry import load_model_artifact, list_model_versions
list_model_versions("candidate")
artifact = load_model_artifact("<model_version>", status="candidate")
```

## Deployment is gated

`--deploy` must only put a model into production after it passes the promotion gate (audit item ML-05: Brier skill vs the base rate, AUC confidence interval, class balance, net-of-cost lift, independent holdout) and is registered with a verified `models/MANIFEST.json` (audit item ML-07). A failed gate stops the deploy before anything is copied. Until both land, do not deploy by hand: `ml-engine` serves `no_edge` (no direction, no confidence) for any booster without a manifest whose gate passed.
