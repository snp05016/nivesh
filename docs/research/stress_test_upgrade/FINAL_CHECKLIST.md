# FINAL CHECKLIST

- [ ] `models/db_models.py` updated with `EquityRiskFactors` and `CovarianceMatrices`.
- [ ] Alembic migration generated and applied successfully.
- [ ] Nightly ETL job implemented to scrape/ingest ADV, Volatility, and Macro factors.
- [ ] `vasicek.py` implemented. Unit tests confirm small-cap beta shrinkage.
- [ ] `covariance.py` implemented. Generates both $\Sigma_{normal}$ and $\Sigma_{crisis}$.
- [ ] `covariance.py` applies Ledoit-Wolf shrinkage to ensure positive definiteness.
- [ ] `liquidity.py` implemented. Almgren-Chriss equation handles 60% volume drops.
- [ ] `concentration.py` implemented. Accurately outputs HHI and MRC sorted arrays.
- [ ] `shock_propagation.py` implemented. Conditional expectation logic works.
- [ ] `stress_test.py` refactored. No more hardcoded `beta * nifty_shock` math.
- [ ] `stress_test.py` normalizes outputs into the 6 mandated scores (0-100 or metric).
- [ ] API router accepts `custom_shocks` dict.
- [ ] API router returns new schema without breaking iOS decoding.
- [ ] `StressTestScreen.swift` updated with 2x3 quantitative scorecard.
- [ ] `StressTestScreen.swift` Tornado chart correctly sorts by MRC, not absolute INR.
- [ ] `StressTestScreen.swift` allows custom macro shock inputs.
- [ ] Local tests pass.
- [ ] Deployed to server and E2E validation against historical 2020 COVID crash matches expectations.
