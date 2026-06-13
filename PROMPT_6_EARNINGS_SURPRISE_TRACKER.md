# EARNINGS SURPRISE TRACKER — Autonomous Build for Antigravity CLI

Paste into Antigravity CLI. Do not ask. Build end-to-end.

## GOAL
Track actual vs estimated earnings. Flag companies that beat/missed by >10%. Show post-earnings price reaction. Build "earnings surprise history" score for each stock. Calendar view + alert on major surprises.

## BACKEND: backend/services/earnings_surprise.py

Endpoint: GET /api/v1/earnings/surprises?period=current_quarter
Endpoint: GET /api/v1/earnings/surprise-history/{ticker}

Logic (zero LLM):
1. Fetch earnings estimates from existing /api/v1/earnings/estimates endpoint
2. Fetch actual results from yfinance .quarterly_earnings or NSE filings
3. Compute surprise: (actual - estimated) / estimated * 100
4. Classify: BEAT (>10%), MISS (<-10%), INLINE (-10% to +10%)
5. Fetch post-earnings price reaction: price change 1 day, 3 days, 5 days after announcement
6. Build historical surprise score per stock: average surprise magnitude, consistency, post-earnings drift
7. Flag "serial beaters" (beat 4+ consecutive quarters) and "serial missers"

Response: [{ticker, company, quarter, estimated_eps, actual_eps, surprise_pct, classification, post_price_1d, post_price_5d, historical_score, serial_pattern}]

## iOS: ios/StockApp/stockme/stockme/Views/EarningsSurpriseScreen.swift

1. Summary hero: "This quarter: 28 beats, 15 misses, 12 inline" with colored bars
2. Biggest surprises: ranked list, most extreme first
3. Each card: ticker, surprise % badge (green BEAT / red MISS / grey INLINE), EPS values, post-earnings price reaction mini-sparkline
4. Serial pattern badges: "4x consecutive beat" in green, "3x miss" in red
5. Calendar view toggle: switch to calendar showing earnings dates with surprise colored dots
6. Tap card -> navigate to StockProfileView, pre-selecting the earnings tab/financials

## RULES
Zero LLM. Reuse /earnings/estimates and yfinance. Store surprises in DB for history. New files only.
