# DATABASE CHANGES

## New Tables to be Created

### 1. `equity_risk_factors`
Stores pre-calculated quantitative attributes for individual stocks. Updated nightly.
- `ticker` (String, Primary Key)
- `beta_market` (Float) - Vasicek-shrunk market beta.
- `beta_oil` (Float) - Vasicek-shrunk sensitivity to Brent crude.
- `beta_rates` (Float) - Vasicek-shrunk sensitivity to Repo rate.
- `beta_fx` (Float) - Vasicek-shrunk sensitivity to USD/INR.
- `average_daily_volume` (Float) - For liquidity penalty calculations.
- `volatility_annualized` (Float) - For marginal risk contributions.
- `base_spread` (Float) - Empirical bid-ask spread constraint.
- `updated_at` (DateTime)

### 2. `covariance_matrices`
Stores serialized matrices to prevent massive re-computation during API requests.
- `matrix_type` (String, Primary Key) - e.g., "NORMAL_252", "CRISIS_1000", "CORR_CRISIS"
- `tickers_list` (JSON) - Ordered list of tickers corresponding to matrix indices.
- `data_matrix` (JSON) - 2D float array representation.
- `updated_at` (DateTime)

## Existing Table Modifications
None directly required. The `Portfolio` table is sufficient for fetching user holdings.
