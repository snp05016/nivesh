# QUANTITATIVE MODEL SPECIFICATIONS

## 1. Vasicek Bayesian Shrinkage
To prevent small-cap stocks from displaying spurious leverage from limited OLS trading history:
1. Calculate $\hat\beta_{i}^{EWMA}$ over 252 days against the Nifty 50.
2. Calculate the variance of this estimate: $\sigma_{\hat\beta_i}^2$.
3. Calculate the average beta of the stock's sector: $\beta_{sector}$, and its variance $\sigma_{sector}^2$.
4. **Shrinkage Function:**
   $$ \beta_i^{Final} = w \cdot \hat\beta_{i}^{EWMA} + (1-w) \cdot \beta_{sector} $$
   $$ w = \frac{\sigma_{sector}^2}{\sigma_{sector}^2 + \sigma_{\hat\beta_i}^2} $$

## 2. Liquidity Penalty (Square-Root Law)
To model evaporating market depth during macro shocks:
1. Fetch current portfolio quantity held for stock $i$: $Q_i$.
2. Fetch 252-day Average Daily Volume (ADV) for stock $i$: $V_i$.
3. Suppress volume by 60% (crisis assumption): $V_{crisis} = V_i \cdot 0.4$.
4. Calculate price impact:
   $$ \Delta P_i = \gamma \cdot \sigma_i \cdot \sqrt{\frac{Q_i}{V_{crisis}}} $$
5. Liquidity Penalty (INR) = $Q_i \cdot \Delta P_i$.
*(Use $\gamma = 0.2$ as standard Indian market impact scalar).*

## 3. Concentration (HHI)
1. Convert all holding values to percentage weights: $w_i$.
2. $$ HHI = \sum_{i=1}^N (w_i \cdot 100)^2 $$

## 4. Conditional Covariance Propagation (Broken Arrow)
When shocking a core factor $f_1$ (e.g. Nifty) by $\Delta f_1$:
1. Unshocked factors $f_2$ update via conditional expectation:
   $$ \Delta f_2 = \mu_2 + \Sigma_{21}\Sigma_{11}^{-1}(\Delta f_1 - \mu_1) $$
2. During Portfolio Aggregation, bypass the default covariance matrix and use the historical $\Sigma_{crisis}$ matrix (derived from the bottom decile of trading days) to compute aggregate variance and Marginal Risk Contributions (MRC).
