# GAP ANALYSIS

Comparison of `CURRENT_STATE.md` vs `SPEC_REQUIREMENTS.md`.

## 1. Core Mathematical Paradigm
- **REQ-MATH-01 (Tier 2.5 Architecture):** **MISSING**. Current `stress_test.py` is Tier 0.
- **REQ-MATH-02 (Base Impact with factor betas):** **REFACTOR_REQUIRED**. `services/stress_test.py:119` currently calculates `beta * nifty_shock`. Must be refactored to sum across a vector of macro factors.
- **REQ-MATH-03 (Liquidity Penalty):** **MISSING**. No subtraction of liquidity cost in `run_stress_test()`.
- **REQ-MATH-04 (HHI and MRC Scores):** **MISSING**. Not calculated or returned to the UI.

## 2. Factor Estimation & Shrinkage
- **REQ-BETA-01 (EWMA OLS Betas):** **MISSING**. Currently relies entirely on a single static `beta` from `yfinance_client._yf_fetch_info` (`info.get("beta")`).
- **REQ-BETA-02 (Vasicek Bayesian Shrinkage):** **MISSING**. No mathematical engine exists for this.
- **REQ-BETA-03 (Daily Caching of Betas):** **MISSING**. The system currently fetches `beta` live synchronously during the HTTP request loop in `run_stress_test`.

## 3. Scenario Engine & Covariance
- **REQ-SCEN-01 (Historical & Hypothetical Scenarios):** **PARTIAL**. `SCENARIOS_DEF` exists in `stress_test.py`, but it operates on arbitrary hardcoded values rather than historical replay vectors. Custom scenario endpoint is not implemented to accept user vectors.
- **REQ-SCEN-02 (Covariance Matrices - Normal & Crisis):** **MISSING**. `portfolio_correlation.py` calculates a single Pearson matrix, but there is no concept of a 1000-day crisis covariance matrix.
- **REQ-SCEN-03 (Broken Arrow Heuristic):** **MISSING**. No matrix switching logic exists.
- **REQ-SCEN-04 (Conditional Shock Propagation):** **MISSING**. The math to propagate $f_2$ from $\Delta f_1$ using $\Sigma_{21}\Sigma_{11}^{-1}$ is entirely absent.

## 4. Liquidity Risk Engine
- **REQ-LIQ-01 (Almgren-Chriss Square-Root Law):** **MISSING**.
- **REQ-LIQ-02 (NSE Impact Cost variables):** **MISSING**. The database (`models/db_models.py`) does not store Average Daily Volume ($V_i$) or daily volatility for individual tickers.
- **REQ-LIQ-03 (Volume Suppression in Crises):** **MISSING**.

## 5. Concentration & Attribution Engine
- **REQ-CONC-01 (HHI):** **MISSING**.
- **REQ-CONC-02 (Marginal Risk Contribution):** **MISSING**.
- **REQ-CONC-03 (Most Vulnerable Holdings sorting):** **PARTIAL**. The current API sorts by `impact_inr`, but this is a static linear calculation, not a true Marginal Risk Contribution leveraging covariance.

## 6. Required User-Facing Outputs
- **REQ-OUT-01 (Risk Score):** **MISSING**.
- **REQ-OUT-02 (Stress Score):** **MISSING**.
- **REQ-OUT-03 (Macro Fragility Score):** **MISSING**.
- **REQ-OUT-04 (Liquidity Score):** **MISSING**.
- **REQ-OUT-05 (Concentration Score):** **MISSING**.
- **REQ-OUT-06 (Tail Risk Score):** **MISSING**.
- *Evidence:* `ios/StockApp/stockme/stockme/Views/StressTestScreen.swift` only defines `impactPct`, `impactInr`, and an array of `holdings`.

## 7. Data Engineering & Pipelines
- **REQ-DATA-01 (Nightly ETL for NSE Bhavcopy, FII flows, RBI):** **MISSING**. Only end-of-day prices are fetched currently. `FIIDIIFlow` model exists but is not wired to the stress test engine.
- **REQ-DATA-02 (Nightly Covariance Batch processing):** **MISSING**.
- **REQ-DATA-03 (Z-Score Normalization):** **MISSING**.
