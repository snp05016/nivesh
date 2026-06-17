# IMPLEMENTATION ORDER

The implementation must proceed strictly in this order to prevent downstream breakages and ensure mathematical outputs can be validated iteratively.

1. **Database & Infrastructure**
   - Create ORM models (`EquityRiskFactors`, `CovarianceMatrices`).
   - Create Alembic migrations.

2. **Data Acquisition Pipelines**
   - Build the ETL scripts to populate the new DB tables nightly.

3. **Core Math Engines (Isolated Development)**
   - Build `vasicek.py`, `covariance.py`, `liquidity.py`, and `concentration.py` as pure functions without tying them to the FastAPI endpoints yet.
   - Write unit tests for each engine using static numpy arrays.

4. **Integration Layer**
   - Build `shock_propagation.py`.
   - Wire all math engines together inside `services/stress_test.py`.

5. **API Presentation**
   - Update `routers/stress_test.py` Pydantic models.
   - Map the math engine outputs to the JSON response schema.

6. **Frontend Consumption**
   - Update Swift Codable models in `StressTestScreen.swift`.
   - Build the UI components (2x3 scorecard, custom sliders, updated charts).

7. **Validation & Tuning**
   - Execute the 2008 and 2020 historical replays.
   - Tune the liquidity scalar $\gamma$ and Vasicek prior variance until outputs align with reality.
