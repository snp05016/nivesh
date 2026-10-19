# iOS App — Complete API Endpoint Inventory

Total: **96 unique endpoint paths** (89 actual API calls, 3 error tracking, 1 diagnostic display, 1 commented-out, 2 dynamic from backend)

---

## Auth & User

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 1 | POST | `/login` | `NetworkManager.swift:192` | Actual |
| 2 | POST | `/register` | `NetworkManager.swift:214` | Actual |
| 3 | GET | `/health` | `NetworkManager.swift:763` | Actual |

## Analysis

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 4 | POST | `/analyze` | `NetworkManager.swift:232,337` | Actual |
| 5 | GET | `/analyze/job/{jobId}` | `NetworkManager.swift:355,370` | Actual |
| 6 | POST | `/analyze/{jobId}/cancel` | `NetworkManager.swift:380` | Actual |
| 7 | GET | `/analyze/active` | `NetworkManager.swift:393` | Actual |

## Backtest

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 8 | POST | `/analysis/backtest` | `StrategyLabScreen.swift:143` | Actual |

## Brainstorm

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 9 | POST | `/brainstorm` | `NetworkManager.swift:1395` | Actual |

## Copilot

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 10 | POST | `/api/v1/copilot/chat` | `CopilotScreen.swift:450` | Actual |

## Dashboard / Home Feed

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 11 | GET | `/api/v1/home-feed` | `HomeFeedService.swift:9` | Actual |
| 12 | GET | `/api/v1/dashboard/stream` | `DialecticProgressView.swift:40` | Actual |

## Earnings

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 13 | GET | `/api/v1/earnings/progress` | `NetworkManager.swift:1202` | Actual |
| 14 | GET | `/api/v1/earnings/feed` | `NetworkManager.swift:1208` | Actual |
| 15 | GET | `/api/v1/earnings/calendar` | `NetworkManager.swift:1216` | Actual |
| 16 | GET | `/api/v1/earnings/estimates` | `NetworkManager.swift:1221` | Actual |
| 17 | GET | `/api/v1/earnings/post-result-movers` | `NetworkManager.swift:1226` | Actual |
| 18 | POST | `/api/v1/earnings/alerts` | `NetworkManager.swift:1234` | Actual |
| 19 | GET | `/api/v1/earnings/surprises` | `EarningsSurpriseScreen.swift:57` | Actual |
| 20 | GET | `/earnings-calendar` | `NetworkManager.swift:718` | Actual |

## Fundamentals (api/v1)

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 21 | GET | `/api/v1/fundamentals/financials` | `NetworkManager.swift:892` | Actual |
| 22 | GET | `/api/v1/fundamentals/shareholding` | `NetworkManager.swift:900` | Actual |
| 23 | GET | `/api/v1/fundamentals/corporate-actions` | `NetworkManager.swift:908` | Actual |
| 24 | GET | `/api/v1/fundamentals/valuation` | `NetworkManager.swift:916` | Actual |
| 25 | GET | `/api/v1/fundamentals/risk-signals` | `NetworkManager.swift:924` | Actual |

## Fundamentals (legacy)

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 26 | GET | `/fundamentals/{ticker}/financials` | `FundamentalsService.swift:44` | Actual |
| 27 | GET | `/fundamentals/{ticker}/shareholding` | `FundamentalsService.swift:48` | Actual |
| 28 | GET | `/fundamentals/{ticker}/corporate-actions` | `FundamentalsService.swift:52` | Actual |
| 29 | GET | `/fundamentals/{ticker}/valuation` | `FundamentalsService.swift:56` | Actual |
| 30 | GET | `/fundamentals/{ticker}/risk-signals` | `FundamentalsService.swift:60` | Actual |
| 31 | GET | `/fundamentals/piotroski/{ticker}` | `NetworkManager.swift:873` | Actual |

## Harvest

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 32 | GET | `/harvester/feed` | `NetworkManager.swift:1357` | Actual |
| 33 | GET | `/harvester/governance/{ticker}` | `NetworkManager.swift:1374` | Actual |
| 34 | GET | `/harvester/sources` | `NetworkManager.swift:1387` | Actual |

## Ideas & Experts

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 35 | GET | `/api/v1/ideas/advisors` | `NetworkManager+Sidebar.swift:332` | Actual |
| 36 | GET | `/api/v1/ideas/feed` | `NetworkManager+Sidebar.swift:344` | Actual |
| 37 | GET | `/api/v1/experts` | `ExpertNetworkView.swift:109` | Actual |
| 38 | GET | `/api/v1/expert-posts` | `ExpertNetworkView.swift:122` | Actual |

## Macro

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 39 | GET | `/macro-impact/{userId}` | `NetworkManager.swift:972` | Actual |
| 40 | GET | `/daily-action/{userId}` | `NetworkManager.swift:982` | Actual |
| 41 | GET | `/macro-context/{ticker}` | `NetworkManager.swift:1306` | Actual |
| 42 | GET | `/macro-strip` | `NetworkManager.swift:730` | Actual |

## Market Data (api/v1)

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 43 | GET | `/api/v1/market/pulse` | `NetworkManager+Sidebar.swift:62` | Actual |
| 44 | GET | `/api/v1/market/momentum` | `NetworkManager+Sidebar.swift:87` | Actual |
| 45 | GET | `/api/v1/market/macro-alternatives` | `NetworkManager+Sidebar.swift:112` | Actual |
| 46 | GET | `/api/v1/market/institutional-flow` | `NetworkManager+Sidebar.swift:137` | Actual |
| 47 | GET | `/api/v1/market/dashboard` | `NetworkManager+Sidebar.swift:162` | Actual |
| 48 | GET | `/api/v1/market/dashboard-pulse` | `NetworkManager+Sidebar.swift:189` | Actual |
| 49 | GET | `/api/v1/market/sector-rotation` | `SectorRotationScreen.swift:45` | Actual |
| 50 | GET | `/api/v1/market/stock-history` | `NetworkManager.swift:785` | Actual |
| 51 | GET | `/api/v1/market/top-movers` | `TechnicalMomentumView.swift:409` | Actual |
| 52 | GET | `/api/v1/market/anomalies` | `MarketAnomalyScreen.swift:40` | Actual |

## Market Data (legacy)

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 53 | GET | `/market-indices` | `NetworkManager.swift:524` | Actual |
| 54 | GET | `/sector-performance` | `NetworkManager.swift:644` | Actual |
| 55 | GET | `/nifty-history` | `NetworkManager.swift:685` | Actual |

## Morning Summary

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 56 | GET | `/morning-summary/{userId}` | `NetworkManager.swift:502` | Actual |

## Notifications

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 57 | POST | `/notifications/register-device` | `NetworkManager.swift:995` | Actual |
| 59 | POST | `/notifications/morning-summary-push` | `NetworkManager.swift:1026` | Actual |

## Options

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 60 | POST | `/api/v1/options/payoff` | `NetworkManager.swift:1325` | Actual |

## Portfolio (legacy)

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 61 | GET | `/portfolio/{userId}` | `NetworkManager.swift:427` | Actual |
| 62 | POST | `/portfolio` | `NetworkManager.swift:466` | Actual |
| 63 | PUT | `/portfolio/note` | `NetworkManager.swift:488` | Actual |
| 64 | DELETE | `/portfolio/remove` | `NetworkManager.swift:578` | Actual |
| 65 | PUT | `/portfolio/update` | `NetworkManager.swift:589` | Actual |
| 66 | GET | `/portfolio/export/excel/{userId}` | `NetworkManager.swift:658` | Actual |
| 67 | GET | `/portfolio/export/pdf/{userId}` | `NetworkManager.swift:669` | Actual |
| 68 | GET | `/portfolio/benchmark` | `NetworkManager.swift:677` | Actual |
| 69 | GET | `/portfolio/signal-warnings` | `NetworkManager.swift:752` | Actual |
| 70 | GET | `/portfolio/risk-analysis/{userId}` | `NetworkManager.swift:952` | Actual |
| 71 | GET | `/portfolio/red-flags/{userId}` | `NetworkManager.swift:962` | Actual |
| 72 | GET | `/portfolio/timeframe-conflicts/{userId}` | `NetworkManager.swift:1073` | Actual |
| 73 | GET | `/portfolio/correlation` | `CorrelationMatrixScreen.swift:138` | Actual |

## Portfolio (api/v1)

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 74 | POST | `/api/v1/portfolio/stress-test` | `StressTestScreen.swift:211` | Actual |
| 75 | GET | `/api/v1/portfolio/stress-test/{jobId}` | `StressTestScreen.swift:298` | Actual |
| 76 | GET | `/api/v1/portfolio/charts/{userId}` | `NetworkManager.swift:1258` | Actual |
| 77 | GET | `/api/v1/portfolio/advisor-consensus` | `NetworkManager.swift:1278` | Actual |
| 78 | GET | `/api/v1/portfolio/valuation-history` | `NetworkManager.swift:1290` | Actual |

## Price Alerts

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 79 | POST | `/alerts/add` | `NetworkManager.swift:603` | Actual |
| 80 | GET | `/alerts/{userId}` | `NetworkManager.swift:614` | Actual |
| 81 | DELETE | `/alerts/remove` | `NetworkManager.swift:623` | Actual |
| 82 | GET | `/alerts/check/{userId}` | `NetworkManager.swift:633` | Actual |

## Quant Lab

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 83 | GET | `/api/v1/stocks/{symbol}/ml-signal` | `QuantLabAPIClient.swift:13` | Actual |
| 84 | GET | `/api/v1/predictions/calibration` | `QuantLabAPIClient.swift:23` | Actual |
| 85 | GET | `/api/v1/predictions/pillar-attribution` | `QuantLabAPIClient.swift:33` | Actual |
| 86 | GET | `/api/v1/predictions/model-versions` | `QuantLabAPIClient.swift:43` | Actual |
| 87 | POST | `/api/v1/backtests/alpha-validation` | `QuantLabAPIClient.swift:51` | Actual |
| 88 | GET | `/api/v1/backtests/strategy-sweep` | `QuantLabAPIClient.swift:86` | Actual |
| 89 | POST | `/api/v1/backtests/regime-breakdown` | `QuantLabAPIClient.swift:94` | Actual |
| 90 | GET | `/api/v1/backtests/cost-sensitivity` | `QuantLabAPIClient.swift:129` | Actual |

## Screener

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 91 | POST | `/api/v1/screener/natural-language` | `NLScreenerScreen.swift:35` | Actual |
| 92 | GET | `/screener` | `NetworkManager.swift:1083` | Actual |

## Search

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 93 | GET | `/search` | `NetworkManager.swift:934` | Actual |

## Stock Profile

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 94 | GET | `/api/v1/stock-profile` | `NetworkManager.swift:819` | Actual |
| 95 | GET | `/quick-info` | `NetworkManager.swift:773` | Actual |
| 96 | GET | `/analyst-ratings` | `NetworkManager.swift:741` | Actual |
| 97 | GET | `/quarterly-financials` | `NetworkManager.swift:697` | Actual |
| 98 | GET | `/dividends/{ticker}` | `NetworkManager.swift:856` | Actual |
| 99 | GET | `/market/sentiment-trend/{ticker}` | `NetworkManager.swift:864` | Actual |

## Trade Journal

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 100 | GET | `/trade-journal/{userId}` | `NetworkManager.swift:1095` | Actual |
| 101 | POST | `/trade-journal` | `NetworkManager.swift:1110` | Actual |
| 102 | PUT | `/trade-journal/{entryId}` | `NetworkManager.swift:1126` | Actual |
| 103 | DELETE | `/trade-journal/{entryId}` | `NetworkManager.swift:1136` | Actual |
| 104 | GET | `/trade-journal/{userId}/stats` | `NetworkManager.swift:1144` | Actual |

## Watchlist

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 105 | POST | `/watchlist/add` | `NetworkManager.swift:539` | Actual |
| 106 | DELETE | `/watchlist/remove` | `NetworkManager.swift:552` | Actual |
| 107 | GET | `/watchlist/{userId}` | `NetworkManager.swift:562` | Actual |

## YouTube

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 108 | GET | `/api/v1/youtube/summary/{videoId}` | `NetworkManager.swift:1418` | Actual |
| 109 | POST | `/api/v1/youtube/summary` | `NetworkManager.swift:1427` | Actual |

## Admin

| # | Method | Endpoint | Source | Type |
|---|--------|----------|--------|------|
| 110 | GET | `/api/v1/admin/error-logs` | `NetworkManager+Sidebar.swift:211` | Actual |
| 111 | GET | `/api/v1/admin/earnings-errors` | `NetworkManager+Sidebar.swift:301` | Actual |
| 112 | POST | `/api/v1/admin/harvest-youtube` | `NetworkManager.swift:1050` | Actual |

---

## Non-Actual References

| # | Endpoint | Source | Type |
|---|----------|--------|------|
| — | `/api/v1/earnings/feed` | `BanknoteErrorCanvas.swift:384` | Error tracking label |
| — | `/api/v1/ideas/feed` | `ExpertNetworkView.swift:188` | Error tracking label |
| — | `/api/v1/notifications/register` | `NotificationManager.swift:68` | Error tracking label |
| — | `/api/v1/screener?preset={id}` | `EarningsDashboardView.swift:1254` | Diagnostic display |
| — | `/api/v1/unlisted/companies` | `PreIPOMarketplaceView.swift:54` | Commented out (planned) |
| — | Dynamic chart URLs | `PortfolioScreen.swift:2159,2243` | Backend-driven from API response |

---

*Generated: June 2026* | *Source: `ios/StockApp/`*
