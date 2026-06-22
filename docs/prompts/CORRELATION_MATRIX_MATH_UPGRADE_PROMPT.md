# Feature Blueprint: Pure Quantitative Portfolio Optimizer & Correlation Matrix Upgrade

## 1. Objective
Refactor and upgrade the existing `correlation_engine.py` to use institutional-grade mathematical models (Modern Portfolio Theory) instead of hardcoded if/else rules or AI LLMs. The engine must dynamically calculate the mathematically optimal sector/asset to add to minimize portfolio variance.

---

## 2. Mathematical Requirements (Strict Rules)

### 2.1 Calculate Aggregate Portfolio Returns
Instead of only calculating individual stock returns, you must compute the **Aggregate Daily Portfolio Return Array**.
- Weight the historical daily returns of each holding by their actual capital allocation (`shares * buy_price`).

### 2.2 Define a Global Sector Proxy Universe
Maintain a static dictionary of liquid benchmark index tickers representing different asset classes and sectors.
- Example: `^CNXIT` (IT), `^NSEBANK` (Bank), `^CNXFMCG` (FMCG), `^CNXPHARMA` (Pharma), `^CNXAUTO` (Auto), `GOLDBEES.NS` (Gold).

### 2.3 Cross-Covariance Optimization (Mean-Variance)
1. Fetch 6 months of historical daily prices for the Global Sector Proxy Universe concurrently alongside the user's holdings.
2. Calculate the **Pearson Correlation Coefficient** between the user's *Aggregate Portfolio Return* and each of the Global Proxies.
3. Calculate the overall **Portfolio Standard Deviation (Volatility)**.
4. Hypothetically assume a 10% cash injection into each proxy, and recalculate the projected portfolio variance.
5. Sort the proxies by which one mathematically reduces the portfolio's standard deviation the most.

### 2.4 Handling NaNs & Missing Data (Pairwise Correlation)
- **DO NOT** use a global `prices.pct_change().dropna()`. If one stock listed a month ago, a global `.dropna()` deletes 5 months of history for the entire matrix.
- You must use `pandas.DataFrame.corr()` which naturally handles pairwise exclusion of NaNs, preserving data for older stocks.

---

## 3. Performance & Architecture Requirements

### 3.1 Asynchronous Data Fetching
- The current implementation blocks execution by calling `yf.Ticker(t).info` sequentially in a loop to fetch sector data. This is a massive bottleneck.
- **Requirement:** You must fetch `yf.Ticker` data asynchronously using `asyncio.gather` and `asyncio.to_thread()`, or cache the sector mappings.

### 3.2 Output Schema
The final output must dynamically inject the mathematically optimal suggestion:
```json
{
  "suggestions": [
    {
      "sector": "FMCG",
      "reason": "Based on covariance math, your portfolio has a high volatility of 18%. Adding FMCG (correlation: -0.12) would mathematically reduce your total volatility to 14.5%.",
      "improvement_score": 85
    }
  ]
}
```

---

## 4. Execution Directives (AGENTS.md)
- Follow the **Sequential Subagent Pipeline**.
- **Builder Agent:** Focus purely on writing the `numpy`/`pandas` math in `services/correlation_engine.py` and making the `yf` calls async.
- **Reviewer Agent:** Verify that `dropna()` is removed from the global dataframe and check the linear algebra calculations.
- **Verifier Agent:** Ensure the FastAPI endpoint returns the correct JSON schema and doesn't time out.
- **No Magic Strings:** All proxy tickers must be stored cleanly at the top of the file.
