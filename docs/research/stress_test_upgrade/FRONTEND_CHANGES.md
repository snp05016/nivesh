# FRONTEND CHANGES

## Location
`ios/StockApp/stockme/stockme/Views/StressTestScreen.swift`

## Model Updates
- Add the `scores` struct/dictionary to `StressTestResult`.
- Add `marginalRiskContribution` and `liquidityPenaltyInr` to `StressTestHolding`.

## UI/UX Additions

### 1. The Quantitative Scorecard
Below the primary Portfolio Impact card, introduce a 2x3 grid displaying the 6 new qualitative metrics:
- **Risk Score**
- **Stress Score**
- **Macro Fragility**
- **Liquidity**
- **Concentration**
- **Tail Risk**
*Styling Requirement:* Must adhere to `Theme.banknoteCard()` and utilize appropriate haptics and coloring (e.g., `Theme.bullGreen` for high resilience, `Theme.bearRed` for high fragility).

### 2. Vulnerability Sorting
The Tornado Chart currently plots the top 10 losers by absolute INR drop.
Modify this to sort by **Marginal Risk Contribution (MRC)** to highlight the true structural drivers of the portfolio's fragility, even if they aren't the largest absolute monetary holdings.

### 3. Custom Shock Input Panel
Add an expandable section to input hypothetical shocks:
- Slider for Nifty 50 (%)
- Slider for Brent Crude (%)
- Slider for RBI Repo Rate (bps)
- Slider for FII Flows (Cr)
