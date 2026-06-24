# LightGBM Baseline Build -- Final Report

**Date:** 2026-06-24
**Status:** Pipeline complete, awaiting data for first training run

---

## Files Changed

| File | Status | Description |
|------|--------|-------------|
| `ml-engine/training/__init__.py` | NEW | Package init exposing public training API |
| `ml-engine/training/feature_builder.py` | NEW | Technical indicator feature engineering (RSI, MACD, Bollinger, ATR, OBV, returns, volatility) with strict no-lookahead guarantees |
| `ml-engine/training/walk_forward.py` | NEW | Anchored walk-forward cross-validation with expanding training window and gap period |
| `ml-engine/training/model_registry.py` | NEW | Versioned model artifact management (save/load/deploy/rollback) |
| `ml-engine/training/evaluation.py` | NEW | Directional accuracy, calibration error, Sharpe proxy, and per-fold metrics |
| `ml-engine/training/train_lightgbm_baseline.py` | NEW | CLI entry point orchestrating the full train-evaluate-deploy pipeline |
| `ml-engine/training/data_adapter.py` | NEW | Data ingestion from CSV/parquet, yfinance live fetch, and synthetic data generation |
| `ml-engine/training/README.md` | NEW | Module-level documentation and usage guide |
| `ml-engine/main.py` | MODIFIED | Added `model_version` tracking to predict and status endpoints |
| `ml-engine/tests/test_training_pipeline.py` | NEW | Unit and integration tests for the full training pipeline |
| `ml-engine/docs/LIGHTGBM_BASELINE_TRAINING.md` | NEW | Detailed design document covering architecture, feature set, and walk-forward methodology |

---

## Endpoints Modified

### POST /predict/single

- Added `model_version` field to response payload (string, e.g. `"v1_20260624_143022"`)
- `ml_engine_mode` value changes to `"trained_lightgbm_baseline"` when a trained model is loaded
- Falls back to `"rule_based"` mode when no trained model is available

### POST /predict/cross-section

- Same changes as `/predict/single` -- `model_version` field added, mode reflects trained vs. fallback

### GET /model/status

- Added `model_version` field indicating the currently deployed model version
- Returns `null` for `model_version` when no trained model is loaded

---

## Model Artifact Behavior

- Trained models are saved to `ml-engine/training/artifacts/<version>/` where `<version>` follows the format `v1_YYYYMMDD_HHMMSS`
- Each artifact directory contains:
  - `lgb_model.txt` -- serialized LightGBM booster
  - `metadata.json` -- training parameters, feature list, fold metrics, calibration stats
  - `feature_config.json` -- feature builder configuration for reproducibility
- Production deployment copies the model to `ml-engine/models/lgb_model.txt`
- The `/predict` endpoints auto-detect the deployed model version at startup by reading the metadata symlink
- Rollback is supported via `model_registry.deploy(version)` pointing to any prior artifact

---

## Tests Added

| Test | Purpose |
|------|---------|
| `test_feature_no_lookahead` | Verifies features at row N use only data from rows 0..N (no future leakage) |
| `test_target_generation_correctness` | Confirms forward-return targets match manual calculation |
| `test_walk_forward_fold_boundaries` | Asserts train/gap/test boundaries never overlap and gap >= configured minimum |
| `test_model_artifact_save_load` | Round-trips a model through save/load and checks prediction equivalence |
| `test_fallback_when_no_model` | Confirms graceful fallback to rule-based mode when no artifact exists |
| `test_predict_single_trained_mode_response` | Validates response schema when trained model is active |
| `test_predict_single_fallback_response` | Validates response schema in fallback mode |
| `test_invalid_ohlcv_input` | Confirms proper error handling for malformed OHLCV data |
| `test_validate_ohlcv` | Tests OHLCV validation logic (missing columns, NaN handling, date parsing) |
| `test_evaluation_empty_input` | Confirms evaluation functions handle empty arrays without crashing |

---

## Training Command

```bash
cd ml-engine
python -m training.train_lightgbm_baseline --data-path data/nse_ohlcv.csv --deploy
```

Options:

| Flag | Description |
|------|-------------|
| `--data-path PATH` | Path to CSV/parquet OHLCV file |
| `--fetch-yfinance` | Download NSE data via yfinance instead of reading a file |
| `--symbols SYMS` | Comma-separated ticker list (default: NIFTY 50 constituents) |
| `--deploy` | Copy trained model to production path after training |
| `--n-folds N` | Number of walk-forward folds (default: 5) |
| `--gap-days N` | Gap period between train and test sets (default: 5) |

---

## Whether Real Data Was Found

**No.** No pre-existing NSE OHLCV dataset was found in the repository. The `data_adapter` module provides three ingestion paths:

1. **CSV/parquet loader** -- for user-provided historical data files
2. **yfinance fetcher** -- downloads NSE-listed equity data live (requires network access)
3. **Synthetic data generator** -- produces realistic OHLCV data for testing and CI

---

## Whether a Real Model Was Trained

**No.** Training requires NSE historical data which must be fetched via yfinance or provided as a CSV file. The pipeline is fully wired and ready to train once data is available. All tests pass using synthetic data to validate pipeline correctness.

---

## Unresolved Issues

| Issue | Severity | Mitigation |
|-------|----------|------------|
| No pre-existing historical data file in the repository | Medium | Use `data_adapter.fetch_nifty500()` or provide CSV manually |
| yfinance fetch requires network access and may be rate-limited | Low | Batch requests with delays; cache downloaded data to `data/` |
| sklearn needed for some evaluation metrics (not in requirements.txt) | Low | Added as optional import; evaluation degrades gracefully without it |
| Docker image may need requirements.txt update for sklearn | Low | Add `scikit-learn>=1.3` to requirements.txt before containerizing |

---

## Next Recommended Task

1. **Fetch data:** Download 5+ years of NIFTY 50 OHLCV data using `data_adapter.fetch_nifty500()`
2. **Train:** Run `python -m training.train_lightgbm_baseline --fetch-yfinance --deploy`
3. **Evaluate:** Review walk-forward metrics and calibration report in the artifact metadata
4. **Gate:** If calibration error < 0.15, deploy to production
5. **Integrate:** Begin TRA regime routing integration to select model based on market regime
