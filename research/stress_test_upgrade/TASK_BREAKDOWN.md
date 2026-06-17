# TASK BREAKDOWN

| Task ID | Objective | Files Affected | Estimated Complexity | Dependencies |
|---------|-----------|----------------|----------------------|--------------|
| **TASK-01** | Create `EquityRiskFactors` and `CovarianceMatrices` DB tables. | `backend/models/db_models.py`, `backend/alembic/` | Low | None |
| **TASK-02** | Create ETL job to fetch volume, spread, and macro factors daily. | `backend/services/nightly_jobs.py`, `backend/services/nse_data_provider.py` | Medium | TASK-01 |
| **TASK-03** | Implement Vasicek Beta Shrinkage math engine. | `backend/services/math_engines/vasicek.py` | High | TASK-02 |
| **TASK-04** | Implement Covariance Matrix Generator ($\Sigma_{normal}$, $\Sigma_{crisis}$). | `backend/services/math_engines/covariance.py` | High | TASK-02 |
| **TASK-05** | Implement Almgren-Chriss Liquidity Penalty engine. | `backend/services/math_engines/liquidity.py` | Medium | TASK-01 |
| **TASK-06** | Implement HHI and MRC (Concentration) engine. | `backend/services/math_engines/concentration.py` | Medium | TASK-04 |
| **TASK-07** | Implement conditional shock propagation (Broken Arrow). | `backend/services/math_engines/shock_propagation.py`| Very High | TASK-04 |
| **TASK-08** | Refactor `run_stress_test` to use new engines and replace hardcoded math. | `backend/services/stress_test.py` | High | TASK-03, 05, 06, 07 |
| **TASK-09** | Update API request/response schemas to include 6 new scores and custom shocks. | `backend/routers/stress_test.py` | Low | TASK-08 |
| **TASK-10** | Update iOS `StressTestScreen.swift` to render new metrics and MRC chart. | `ios/StockApp/stockme/stockme/Views/StressTestScreen.swift` | Medium | TASK-09 |
