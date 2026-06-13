# CORRELATION MATRIX & DIVERSIFICATION SCORE — Autonomous Build

Paste into Antigravity CLI. Do not ask. Build end-to-end.

## GOAL
Compute correlation between all portfolio/watchlist holdings. Find hidden concentration risk. "Your portfolio is 73% Nifty-correlated because 5/7 stocks are Nifty 50 components. You own 3 banks — a rate hike hits 42% of your portfolio."

## BACKEND: backend/services/correlation_engine.py

Endpoint: GET /api/v1/portfolio/correlation?portfolio_id=holdings

Logic (zero LLM, pure numpy):
1. Fetch 3yr daily price history for each holding + Nifty
2. Compute daily returns. Build correlation matrix (numpy.corrcoef)
3. Cluster highly correlated holdings (>0.7 = red, 0.4-0.7 = amber, <0.4 = green)
4. Compute diversification score (0-100). Formula: (1 - avg_correlation) * sector_diversity_bonus
5. Flag concentration risks: "3 of 7 holdings are banks = 42% sector concentration"
6. Suggest: "Adding a pharma stock would improve diversification score from 45 to 62"

Response: {correlation_matrix: [[ticker_a, ticker_b, correlation], ...], diversification_score, sector_concentration: [{sector, weight_pct, holdings}], suggestions: [{sector, reason, improvement_score}]}

## iOS: ios/StockApp/stockme/stockme/Views/CorrelationMatrixScreen.swift

1. Diversification score hero: ring gauge 0-100, green/amber/red
2. Heatmap: grid of colored squares, each cell = correlation between two holdings
3. Sector concentration: pie/donut with "Banks 42% = HIGH RISK" warning
4. Suggestion cards: "Add pharma -> score improves from 45 to 62"

## RULES
Zero LLM. Pure numpy. Reuse yfinance for price history. New files only.
