# MARKET ANOMALY SCANNER — Autonomous Build for Antigravity CLI

Paste into Antigravity CLI. Do not ask. Build end-to-end.

## GOAL
Scan all 200+ NSE stocks for anomalies daily: volume spikes, RSI divergence, price-volume divergence, gap ups/downs, unusual options activity. Flag top 10 anomalies. Backend cron job + iOS dashboard.

## BACKEND: backend/services/anomaly_scanner.py

Runs as APScheduler job every 60 minutes. Zero LLM. Pure factor_engine + yfinance.

Detected anomalies (per stock, per day):
1. VOLUME_SPIKE: volume > 3x 20-day avg. Flag with actual multiple.
2. RSI_DIVERGENCE: price making new high but RSI declining (bearish divergence) or vice versa
3. PRICE_VOLUME_DIVERGENCE: price up 5% but volume declining = hollow rally
4. GAP_UP: open > 3% above previous close. Flag gap size.
5. GAP_DOWN: open < -3% below previous close.
6. UNUSUAL_OPTIONS: PCR (put-call ratio) > 2.0 or < 0.4 (use existing options_scraper)
7. DELIVERY_SPIKE: delivery % > 80% on high-volume day (fetch from NSE bhavcopy)
8. 52W_BREAKOUT: price crossed above 52-week high or below 52-week low
9. CONSECUTIVE_DIRECTION: 5+ consecutive days same direction with increasing volume
10. LOW_FLOAT_SURGE: market cap < 1000Cr AND volume > 5x avg (potential operator activity)

For each anomaly: assign severity (HIGH/MEDIUM/LOW) based on magnitude.

Endpoint: GET /api/v1/market/anomalies?limit=10
Response: [{ticker, company, anomaly_type, severity, detail, price, change_pct, timestamp}]

Store in DB for historical anomaly tracking. Add to scheduler in harvest_worker.py.

## iOS: ios/StockApp/stockme/stockme/Views/MarketAnomalyScreen.swift

1. Today's anomalies: ranked list, most severe first
2. Each card: severity badge (red/amber), anomaly type icon, ticker, detail text, price change
3. Filter by type: horizontal chip selector
4. Tap card -> navigate to StockProfileView
5. Pull-to-refresh triggers re-scan

Add to navigation sidebar.

## RULES
Zero LLM. Reuse factor_engine.py for RSI/SMA/Bollinger. Reuse options_scraper for PCR. New files only.
