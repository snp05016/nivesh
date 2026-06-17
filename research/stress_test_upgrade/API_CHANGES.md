# API CHANGES

## Endpoint: `POST /api/v1/portfolio/stress-test`

### Request Modifications
Allow an optional `custom_shocks` dictionary to enable specific macroeconomic testing.
```json
{
  "portfolio_id": "holdings",
  "scenarios": ["NIFTY_CRASH", "CUSTOM"],
  "custom_shocks": {
    "oil": 50.0,
    "rates": 100.0,
    "fii_flow": -50000.0
  }
}
```

### Response Modifications
The current response is an array of scenarios containing `impact_pct` and `impact_inr` and an array of `holdings`.
We must introduce the 6 new qualitative scores per scenario, and augment the `holdings` array.

```json
{
  "results": [
    {
      "name": "NIFTY_CRASH",
      "impact_pct": -22.5,
      "impact_inr": -450000.0,
      "scores": {
        "risk_score": 75,
        "stress_score": 60,
        "macro_fragility": 82,
        "liquidity_score": 45,
        "concentration_score": 30,
        "tail_risk_score": 90
      },
      "holdings": [
        {
          "ticker": "HDFCBANK.NS",
          "impact_pct": -15.0,
          "impact_inr": -150000.0,
          "marginal_risk_contribution": 0.25,
          "liquidity_penalty_inr": -500.0
        }
      ]
    }
  ]
}
```
