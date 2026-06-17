# IMPLEMENTATION ROADMAP

## Phase 1: Data Engineering & Mathematical Foundations
**Objective:** Establish the ETL pipelines and math engines required to support the new quantitative calculations.
**Dependencies:** None.
**Files Affected:**
- `backend/models/db_models.py` (New models for caching betas, covariance, ADV)
- `backend/services/math_engines/vasicek.py` (New)
- `backend/services/math_engines/covariance.py` (New)
- `backend/services/nightly_jobs.py` (Update)
**Database Changes:**
- New table `EquityRiskFactors` (ticker, beta_market, beta_oil, beta_rates, adv, volatility, spread)
- New table `CovarianceMatrices` (matrix_type, json_blob, updated_at)
**Validation Requirements:**
- Unit tests verifying the Vasicek shrinkage equation pulls outlier betas toward sector means.
- Verify daily ETL job correctly ingests FII flows and NSE volume data.

## Phase 2: Scenario Engine & Shock Propagation
**Objective:** Replace the hardcoded `SCENARIOS_DEF` with the predictive covariance shock framework.
**Dependencies:** Phase 1 (Covariance matrices).
**Files Affected:**
- `backend/services/math_engines/shock_propagation.py` (New)
- `backend/services/stress_test.py` (Refactor)
**Validation Requirements:**
- Input a simulated 2020 COVID shock vector and verify the conditional expectation equation outputs a severely degraded Nifty prediction.
- Verify the "Broken Arrow" heuristic successfully swaps to $\Sigma_{crisis}$.

## Phase 3: Liquidity & Concentration Engines
**Objective:** Implement the Almgren-Chriss liquidity penalty and the HHI/MRC concentration metrics.
**Dependencies:** Phase 1 (ADV and Volatility data).
**Files Affected:**
- `backend/services/math_engines/liquidity.py` (New)
- `backend/services/math_engines/concentration.py` (New)
- `backend/services/stress_test.py` (Refactor to subtract liquidity penalty)
**Validation Requirements:**
- A portfolio of illiquid micro-caps must show an exponentially higher liquidity penalty under stress than a portfolio of Nifty 50 large-caps.

## Phase 4: API Restructuring & Score Generation
**Objective:** Expose the new rich metrics (Stress Score, Tail Risk Score, etc.) to the frontend via the API.
**Dependencies:** Phases 1-3.
**Files Affected:**
- `backend/routers/stress_test.py` (Update Pydantic response models)
- `backend/services/stress_test.py` (Compile and normalize the 6 required scores)
**API Changes:**
- Update `StressTestResult` to include `scores` object (risk, stress, macro_fragility, liquidity, concentration, tail_risk).
- Update holding-level items to include `marginal_risk_contribution`.
**Validation Requirements:**
- API returns exactly the JSON contract expected by the updated iOS client.

## Phase 5: Frontend Integration & Visualization
**Objective:** Update the iOS client to consume and beautifully render the new quantitative insights.
**Dependencies:** Phase 4.
**Files Affected:**
- `ios/StockApp/stockme/stockme/Views/StressTestScreen.swift`
**Frontend Changes:**
- Add radial gauges or progress bars for the 6 new scores.
- Sort the "Holding Impact" section by Marginal Risk Contribution (MRC).
- Allow user input for custom macro factor shocks if the backend supports it.
**Validation Requirements:**
- E2E testing on device. Ensure rendering does not break under extreme values (e.g., negative scores, extreme drawdowns).
