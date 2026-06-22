# CURRENT STATE ANALYSIS

## 1. Existing Stress Testing Implementation (`backend/services/stress_test.py`)
**Architecture:** Tier 0 / Tier 1 (Extremely basic)
**Methodology:**
- Hardcoded list of scenarios (`nifty_crash`, `oil_shock`, `rate_hike`, etc.) with static `nifty_shock` (%) and additive `sector_shocks`.
- Linear summation: `impact_pct = (beta * nifty_shock) + sector_adj`.
- Calculates static `impact_inr` and aggregates up to a portfolio-level total impact percentage.

**Limitations:**
- Uses a single static `beta` fetched from `yfinance` via `_yf_fetch_info` (`info.get("beta", 1.0)`).
- Sectors are loosely guessed using basic substring matching on `company_name` (e.g., matching "tcs" -> "IT").
- No covariance modeling, no correlation breakdown, no historical simulation, no fat-tail adjustments.
- Missing any form of liquidity penalty (impact cost modeling).

## 2. Current Portfolio & Holdings System (`backend/models/db_models.py`)
**Holdings & Watchlist:**
- Modeled in the `Portfolio` table.
- Dual-purpose: `group_name='holdings'` (requires `shares > 0`, `buy_price > 0`) vs. `group_name='watchlist'` (uses `shares = 0`, `buy_price = 0`).
- Tied to `user_id`, tracks `ticker`, `shares`, `buy_price`, `purchase_date`.
- No historical transactional data inherently tracked here for risk replay, just the current snapshot, though `portfolio_valuation_history` and `trade_journal` exist.

**Net Worth Tracking:**
- `NetWorthLedger` and `PortfolioValuationHistory` tables exist to track daily snapshots.

## 3. Mathematical Engines & Factor Models (`backend/services/math_engines/`)
- **Correlation:** `portfolio_correlation.py` exists and computes a basic Pearson correlation matrix over the last 63 trading days. Does not use DCC-GARCH or model correlation breakdown during hectics periods.
- **Factor Models:** Nothing matches the "Vasicek Shrinkage" or "Kalman Filter" beta calculations mentioned in the spec.
- **Risk Metrics:** `auditor_risk.py`, `conformal_prediction.py`, `minsky_risk.py`, etc., exist but are unrelated to macroeconomic shock propagation.

## 4. API Architecture (`backend/routers/stress_test.py`)
- Single endpoint `POST /api/v1/portfolio/stress-test`.
- Payload takes `scenarios: List[str]` and `portfolio_id: str`.
- Simply calls `run_stress_test(holdings, scenarios)` and returns an array of `results`.
- Does not accept custom macro factor shocks (e.g., Oil +20%, Rate +50bps).

## 5. Frontend Architecture (`ios/StockApp/stockme/stockme/Views/StressTestScreen.swift`)
- Single view with hardcoded scenario chips ("NIFTY_CRASH", "OIL_SHOCK", etc.).
- Users can select up to 3 scenarios.
- Hits the `/stress-test` endpoint.
- Displays a summary card (total INR and % loss) and a Tornado Chart (BarMark) of the top 10 impacted holdings.
- Does not display Concentration Score, Liquidity Score, Tail Risk Score, or Macro Fragility Score.
