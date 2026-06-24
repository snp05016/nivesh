# Dataset Readiness

### 1. Data Source
The training data expects OHLCV inputs aggregated by symbol and date. Nivesh uses `jugaad-data` via `backend/services/nse_data_provider.py` to fetch historical Bhavcopy, but the data must be materialized and persisted (e.g., to a `.parquet` file) before passing into `build_feature_matrix()`.

### 2. Feature Completeness
- `feature_builder.py` computes all 158 Alpha158 features + 8 custom momentum/volatility features.
- Missing values in historical windows (e.g., `ROC60` on a stock with 30 days of data) will yield NaNs. LightGBM handles NaNs gracefully via `use_missing=true`, but the `min_history=120` parameter aggressively filters out recent IPOs.

### 3. Sector One-Hot Encoding
`feature_builder.py` attempts to one-hot encode sectors if a `sector` column is present. The `nse_data_provider` currently does not append sector meta-information cleanly to the time series. This requires a join against the `db_models.Ticker` table before training.

### Readiness Status: ⚠️ Needs Consolidation
The dataset generation requires a dedicated `dataset_builder.py` that connects `nse_data_provider` to the `feature_builder` and writes out `training_data.parquet`.
