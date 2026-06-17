# SPECIFICATION REQUIREMENTS MATRIX

Extracted directly from `Indian_Equity_Stress_Test_Engine.md`.

## 1. Core Mathematical Paradigm
- **REQ-MATH-01:** Implement a Tier 2.5 Hybrid Architecture (combining Predictive Stress Models with Econometric techniques).
- **REQ-MATH-02:** Calculate base stock impact as: `Base Impact = Alpha + Sum(Beta * Delta_Factor)`.
- **REQ-MATH-03:** Calculate Total Portfolio Loss as: `Base Loss - Liquidity Penalty`.
- **REQ-MATH-04:** Generate concentration and vulnerability scores based on Herfindahl-Hirschman Index (HHI) and Marginal Risk Contribution (MRC).

## 2. Factor Estimation & Shrinkage (The Beta System)
- **REQ-BETA-01:** Calculate raw asset sensitivities ($\beta$) against macro/market factors using Exponentially Weighted Moving Average (EWMA) OLS.
- **REQ-BETA-02:** Apply Vasicek Bayesian Shrinkage to pull statistically insignificant small-cap betas toward their respective sector means.
- **REQ-BETA-03:** Store and cache these shrunk betas daily for 2000+ Indian equities.

## 3. Scenario Engine & Covariance
- **REQ-SCEN-01:** Support both historical stress replay (2008 GFC, 2020 COVID, 2022 Inflation, 2024 Election) and hypothetical scenarios (e.g., Oil +50%, RBI +100bps).
- **REQ-SCEN-02:** Utilize the "Broken Arrow" stress heuristic. Maintain two covariance matrices: $\Sigma_{normal}$ (252-day) and $\Sigma_{crisis}$ (1000-day or specific historical crash regimes).
- **REQ-SCEN-03:** During a stress test, aggressively swap to the $\Sigma_{crisis}$ covariance matrix to model correlation breakdowns (where all assets correlate toward 1.0).
- **REQ-SCEN-04:** Compute conditional shock propagation for unshocked factors using the covariance matrix.

## 4. Liquidity Risk Engine
- **REQ-LIQ-01:** Implement Almgren-Chriss Square-Root Law of Market Impact.
- **REQ-LIQ-02:** Liquidity Penalty equation requires Average Daily Volume ($V_i$), Shares Held ($Q_i$), daily volatility ($\sigma_i$), and base bid-ask spread.
- **REQ-LIQ-03:** In crisis scenarios, artificially suppress assumed volume $V_i$ by 60% (multiply by 0.4) to simulate evaporating market depth.

## 5. Concentration & Attribution Engine
- **REQ-CONC-01:** Calculate Herfindahl-Hirschman Index (HHI) for the portfolio. (HHI < 1500 = Diversified, > 2500 = Concentrated).
- **REQ-CONC-02:** Calculate Marginal Risk Contribution (MRC) for each asset using $\Sigma_{crisis}$.
- **REQ-CONC-03:** Identify the "Most Vulnerable Holdings" by sorting absolute Risk Contribution ($w_i \times MRC_i$).

## 6. Required User-Facing Outputs
- **REQ-OUT-01:** **Risk Score (0-100)**: Unconditional standard deviation mapped to sigmoid.
- **REQ-OUT-02:** **Stress Score (0-100)**: Expected Shortfall percentile rank relative to Nifty 50.
- **REQ-OUT-03:** **Macro Fragility Score**: Weighted aggregation of macro betas (Inflation, Repo, Brent, USDINR).
- **REQ-OUT-04:** **Liquidity Score**: Expected percentage slippage to liquidate in 2 days under stress.
- **REQ-OUT-05:** **Concentration Score**: Logarithmic mapping of HHI.
- **REQ-OUT-06:** **Tail Risk Score**: Divergence between Parametric VaR and Expected Shortfall.

## 7. Data Engineering & Pipelines
- **REQ-DATA-01:** Nightly ETL pipeline fetching NSE Bhavcopy (for ADV/Volume), NSDL FII/DII flows, RBI macroeconomic datasets.
- **REQ-DATA-02:** Nightly batch processing of Covariance Matrices ($\Sigma_{normal}$, $\Sigma_{crisis}$).
- **REQ-DATA-03:** Normalization of extreme variables (e.g., FII flows) using 252-day rolling Z-scores.
