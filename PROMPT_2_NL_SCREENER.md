# NATURAL LANGUAGE SCREENER — Autonomous Build for Antigravity CLI

Paste into Antigravity CLI. Do not ask. Build end-to-end.

## GOAL
"Find stocks like HDFC Bank but PE under 20 and promoter holding above 50%"
User types natural language. DeepSeek parses to structured filters. Runs existing screener. Returns results.

## BACKEND: backend/services/nl_screener.py

Single endpoint: POST /api/v1/screener/natural-language
Request: {query: "find pharma stocks with ROCE > 15% and debt below 1.0"}
Response: {parsed_filters: {sector, pe_max, promoter_min, roce_min, ...}, results: [ticker, company, score, reason]}

Logic:
1. DeepSeek (1 call, temp=0): parse NL query -> structured JSON with filter keys
2. Map to existing GET /screener presets or build custom SQL query
3. Return parsed_filters (show user what we understood) + results
4. Cache identical queries for 1hr

DeepSeek system prompt: "You parse natural language stock screening queries into structured filters. Return ONLY valid JSON. Available filters: sector, industry, pe_max, pe_min, market_cap_min, market_cap_max, promoter_holding_min, fii_holding_min, dii_holding_min, roce_min, roe_min, debt_to_equity_max, ebitda_margin_min, dividend_yield_min, price_change_3m_min, price_change_1y_min, rsi_min, rsi_max, keyword (free text search in company name/description). If user mentions a company by name (e.g. 'like HDFC Bank'), extract that company's metrics as reference values."

## iOS: ios/StockApp/stockme/stockme/Views/NLScreenerScreen.swift

Layout:
1. Search bar at top: "Ask in plain English..." with mic button
2. Results: parsed filter pills showing what was understood
3. Stock cards: ticker, company name, sector, key metrics, match score badge
4. Tap card -> navigate to StockProfileView
5. History: last 5 queries stored locally

Add to navigation sidebar.

## RULES
One DeepSeek call per query. temp=0 for deterministic parsing. Cache identical queries. Reuse existing screener infrastructure. New files only.
