# iOS Frontend Views to FastAPI Backend Endpoints Mapping

This document provides a comprehensive mapping of every core view/screen in the Nivesh iOS application to its corresponding FastAPI backend endpoints.

---

## 1. Stock Profile View
Displays company details, real-time or historical pricing, shareholding patterns, financials, and recommendations.

| Screen/Component in iOS | Backend API Endpoint | Method | Response Schema / Type | Key Fields / Formatting Rules |
| :--- | :--- | :--- | :--- | :--- |
| Core Stock Details Card | `/api/v1/stock-profile` | GET | `StockProfileResponse` | Flat response. Scales `market_cap_crores` to Crores. |
| Quick Info Header | `/quick-info` | GET | Raw Dict | Returns short overview, PE ratio, day change. |
| Price Charts | `/api/v1/market/stock-history` | GET | Raw Dict | Price points for different time periods (1d, 1y, etc.). |
| Financials Table | `/quarterly-financials` | GET | Raw Dict | Revenue and profit scaled to Crores. |
| Sentiments / Analyst Ratings | `/analyst-ratings` | GET | Raw Dict | Buy/Sell/Hold percentages and targets. |
| Dividends History | `/dividends/{ticker}` | GET | Raw Dict | Uses `format_indian_currency` for yield and payout. |
| Sentiment Trend Chart | `/market/sentiment-trend/{ticker}` | GET | Raw Dict | Track sentiment change over time. |
| Piotroski Score Card | `/fundamentals/piotroski/{ticker}` | GET | Raw Dict | 9-point score showing financial strength. |
| Macro Context Summary | `/macro-context/{ticker}` | GET | Raw Dict | Sector/FII flows affecting the stock. |

---

## 2. AI Analysis View
Spawns and monitors the multi-agent dialectical research loop.

| Screen/Component in iOS | Backend API Endpoint | Method | Response Schema / Type | Key Fields / Formatting Rules |
| :--- | :--- | :--- | :--- | :--- |
| Analysis Request Screen | `/analyze` | POST | `AnalyzeRequest` (req) | Spawns asynchronous job in subprocess worker. |
| Job Polling / Progress | `/analyze/job/{job_id}` | GET | Raw Dict | Polls status/checkpoint. Validates job owner (IDOR guard). |
| Active Job Tracker | `/analyze/active` | GET | Raw Dict | Drives global loader in iOS client. |
| Cancel Job Button | `/analyze/{job_id}/cancel` | POST | Raw Dict | Cancels the active worker process. |

---

## 3. Markets View
Renders index values, crossovers, and earnings calendar progress.

| Screen/Component in iOS | Backend API Endpoint | Method | Response Schema / Type | Key Fields / Formatting Rules |
| :--- | :--- | :--- | :--- | :--- |
| Indices Strip (Nifty, etc.) | `/market-indices` | GET | Raw Dict | Live values of major indices. |
| Index Historical Chart | `/nifty-history` | GET | Raw Dict | Historical closing values of Nifty. |
| Sector Heatmap | `/sector-performance` | GET | Raw Dict | Sectoral performance over different durations. |
| Market Pulse Dashboard | `/api/v1/market/pulse` | GET | Raw Dict | Overall sentiment and trends. |
| Momentum Movers | `/api/v1/market/momentum` | GET | Raw Dict | Stocks hitting highs/lows. |
| Macro Alternative Assets | `/api/v1/market/macro-alternatives` | GET | Raw Dict | Gold, USDINR, Bond Yields. |
| Institutional Flow (FII/DII) | `/api/v1/market/institutional-flow` | GET | Raw Dict | Daily net purchase data. |
| Markets Dashboard Hub | `/api/v1/market/dashboard` | GET | Raw Dict | Aggregate dashboard data. |
| Weightage Indicator | `/api/v1/market/dashboard-pulse` | GET | Raw Dict | Scales index weights to Crores. |
| Legacy Earnings List | `/earnings-calendar` | GET | Raw Dict | Direct query on Portfolio table. |
| Unified Earnings Calendar | `/api/v1/earnings/calendar` | GET | Raw Dict | Dynamic date-based list of results. |
| Results Feed | `/api/v1/earnings/feed` | GET | Raw Dict | Timeline of company earnings declarations. |
| Earnings Season Progress | `/api/v1/earnings/progress` | GET | Raw Dict | Progress of earnings declarations. |
| Moover Post Result | `/api/v1/earnings/post-result-movers` | GET | Raw Dict | High volatility stocks after results. |
| Macro Ticker Strip | `/macro-strip` | GET | Raw Dict | Unified global macro status ticker. |

---

## 4. Ideas View
Provides SEBI recommendations, advisory feed, and thematic brainstorming.

| Screen/Component in iOS | Backend API Endpoint | Method | Response Schema / Type | Key Fields / Formatting Rules |
| :--- | :--- | :--- | :--- | :--- |
| Verified Analysts List | `/api/v1/ideas/advisors` | GET | Raw Dict | Advisor biographies and registration details. |
| Recommendations Feed | `/api/v1/ideas/feed` | GET | Raw Dict | Calls/signals with targets and durations. |
| AI Brainstorm Console | `/brainstorm` | POST | `BrainstormingResponse` | Enforces Indian scale formatting check on LLM ideas. |

---

## 5. News & Home Feed View
Exposes standard news flow, portfolio videos, and custom summaries.

| Screen/Component in iOS | Backend API Endpoint | Method | Response Schema / Type | Key Fields / Formatting Rules |
| :--- | :--- | :--- | :--- | :--- |
| Aggregated Home Feed | `/api/v1/home-feed` | GET | Raw Dict | Combines news, videos, and portfolio tickers. |
| AI Morning Brief Sheet | `/morning-summary/{user_id}` | GET | Raw Dict | Formats user portfolio summary in Lakhs/Crores. |
| harvester Filings Feed | `/harvester/feed` | GET | Raw Dict | Harvested exchange filing announcements. |
| Governance Red Flags | `/harvester/governance/{ticker}` | GET | Raw Dict | Displays corporate governance events/risks. |
| Sources Health Monitor | `/harvester/sources` | GET | Raw Dict | Shows ingestion status of news/exchange sources. |
