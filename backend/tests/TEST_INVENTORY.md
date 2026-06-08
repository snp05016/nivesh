# Nivesh API — Test Inventory

**Generated:** 2026-06-08  
**Total Endpoints:** 84  
**Test File:** `tests/test_api.py`

---

| # | METHOD | Path | Auth Required | Path Params | Query Params | Body Schema | Status |
|---|--------|------|---------------|-------------|--------------|-------------|--------|
| 1 | POST | /login | No | — | — | `{username, password}` | ✅ Tested |
| 2 | POST | /register | No | — | — | `{username, password, display_name}` | ✅ Tested |
| 3 | GET | /ping | No | — | — | — | ✅ Tested |
| 4 | GET | /health | No | — | — | — | ✅ Tested |
| 5 | GET | /health/live | No | — | — | — | ✅ Tested |
| 6 | GET | / | No | — | — | — | ✅ Tested |
| 7 | GET | /dashboard-data | No | — | — | — | ✅ Tested |
| 8 | POST | /api/v1/admin/harvest-youtube | admin | — | — | — | ✅ Tested |
| 9 | POST | /api/v1/admin/harvest-advisors | admin | — | — | — | ✅ Tested |
| 10 | POST | /api/v1/admin/harvest-news | admin | — | — | — | ✅ Tested |
| 11 | GET | /quick-info | No | — | `ticker, exchange` | — | ✅ Tested |
| 12 | POST | /analyze | No | — | — | `{ticker, exchange, user_id?, deep_scan?}` | ✅ Tested |
| 13 | POST | /analyze/batch | No | — | — | `{tickers[], exchange, user_id?}` | ✅ Tested |
| 14 | GET | /analyze/batch/{batch_id} | No | `batch_id` | — | — | ✅ Tested |
| 15 | GET | /api/v1/technical-signals | No | — | `ticker?` | — | ✅ Tested |
| 16 | GET | /api/v1/home-feed | No | — | `user_id?` | — | ✅ Tested |
| 17 | GET | /screener | No | — | `preset?, exchange?` | — | ✅ Tested |
| 18 | GET | /daily-action/{user_id} | **Required** | `user_id` | — | — | ⚠️ xfail (401 bug) |
| 19 | GET | /token-stats | admin | — | — | — | ✅ Tested |
| 20 | POST | /alerts/add | No | — | — | `{user_id, ticker, target_price, direction, company_name?}` | ✅ Tested |
| 21 | DELETE | /alerts/remove | No | — | — | `{user_id, alert_id}` | ✅ Tested |
| 22 | GET | /alerts/check/{user_id} | No | `user_id` | — | — | ✅ Tested |
| 23 | GET | /alerts/{user_id} | No | `user_id` | — | — | ✅ Tested |
| 24 | GET | /portfolio/{user_id} | No | `user_id` | — | — | ⚠️ xfail (500 bug) |
| 25 | GET | /portfolio/history/{user_id} | No | `user_id` | — | — | ✅ Tested |
| 26 | GET | /fundamentals/piotroski/{ticker} | No | `ticker` | — | — | ✅ Tested |
| 27 | GET | /morning-summary/{user_id} | No | `user_id` | — | — | ✅ Tested |
| 28 | POST | /portfolio | No | — | — | `{user_id, ticker, exchange, company_name, shares, buy_price, group_name?}` | ✅ Tested |
| 29 | POST | /portfolio/add | No | — | — | `{user_id, ticker, exchange, company_name, shares, buy_price, group_name?}` | ✅ Tested |
| 30 | DELETE | /portfolio/remove | No | — | — | `{user_id, ticker}` | ✅ Tested |
| 31 | PUT | /portfolio/update | No | — | — | `{user_id, ticker, shares, buy_price}` | ✅ Tested |
| 32 | GET | /portfolio/signal-warnings | No | — | `user_id` | — | ✅ Tested |
| 33 | PUT | /portfolio/note | No | — | — | `{user_id, ticker, note}` | ✅ Tested |
| 34 | GET | /api/v1/portfolio/advisor-consensus | No | — | `user_id` | — | ✅ Tested |
| 35 | GET | /portfolio/export/excel/{user_id} | No | `user_id` | — | — | ✅ Tested |
| 36 | GET | /api/v1/portfolio/valuation-history | No | — | `user_id` | — | ✅ Tested |
| 37 | GET | /portfolio/risk-analysis/{user_id} | No | `user_id` | — | — | ✅ Tested |
| 38 | GET | /portfolio/red-flags/{user_id} | No | `user_id` | — | — | ✅ Tested |
| 39 | GET | /macro-impact/{user_id} | No | `user_id` | — | — | ✅ Tested |
| 40 | GET | /portfolio/timeframe-conflicts/{user_id} | **Required** | `user_id` | — | — | ⚠️ xfail (401 bug) |
| 41 | POST | /trade-journal | No | — | — | `{user_id, ticker, action, price_at_time, reason_text, outcome_text?, company_name?, mood?}` | ✅ Tested |
| 42 | GET | /trade-journal/{user_id} | No | `user_id` | — | — | ✅ Tested |
| 43 | PUT | /trade-journal/{entry_id} | No | `entry_id` | — | `{outcome_text, mood?}` | ✅ Tested |
| 44 | DELETE | /trade-journal/{entry_id} | No | `entry_id` | — | — | ✅ Tested |
| 45 | GET | /trade-journal/{user_id}/stats | No | `user_id` | — | — | ✅ Tested |
| 46 | GET | /portfolio/export/pdf/{user_id} | No | `user_id` | — | — | ✅ Tested |
| 47 | GET | /api/v1/market/net-worth-ledger/{user_id} | **Required** | `user_id` | — | — | ✅ Tested |
| 48 | GET | /market-indices | No | — | — | — | ✅ Tested |
| 49 | GET | /nifty-history | No | — | `period?` | — | ✅ Tested |
| 50 | GET | /quarterly-financials | No | — | `ticker` | — | ✅ Tested |
| 51 | GET | /macro-strip | No | — | — | — | ✅ Tested |
| 52 | GET | /earnings-calendar | No | — | — | — | ✅ Tested |
| 53 | GET | /analyst-ratings | No | — | `ticker` | — | ✅ Tested |
| 54 | GET | /ipo-calendar | No | — | — | — | ✅ Tested |
| 55 | GET | /sector-weekly | No | — | — | — | ✅ Tested |
| 56 | GET | /search | No | — | `q` | — | ✅ Tested |
| 57 | GET | /sector-performance | No | — | — | — | ✅ Tested |
| 58 | GET | /api/v1/market/pulse | No | — | — | — | ✅ Tested |
| 59 | GET | /api/v1/market/momentum | No | — | — | — | ✅ Tested |
| 60 | GET | /api/v1/market/macro-alternatives | No | — | — | — | ✅ Tested |
| 61 | GET | /api/v1/market/institutional-flow | No | — | — | — | ✅ Tested |
| 62 | GET | /api/v1/earnings/sync-ratio | No | — | — | — | ✅ Tested |
| 63 | GET | /api/v1/earnings/yoy-aggregate | No | — | — | — | ✅ Tested |
| 64 | GET | /api/v1/market/dashboard | No | — | — | — | ✅ Tested |
| 65 | GET | /api/v1/market/dashboard-pulse | No | — | — | — | ✅ Tested |
| 66 | GET | /api/v1/market/institutional-leaderboard | No | — | — | — | ✅ Tested |
| 67 | GET | /api/v1/earnings/progress | No | — | — | — | ✅ Tested |
| 68 | GET | /api/v1/earnings/feed | No | — | — | — | ✅ Tested |
| 69 | GET | /api/v1/earnings/calendar | No | — | — | — | ✅ Tested |
| 70 | GET | /api/v1/earnings/estimates | No | — | `ticker` | — | ✅ Tested |
| 71 | GET | /api/v1/earnings/post-result-movers | No | — | — | — | ✅ Tested |
| 72 | GET | /api/v1/earnings/alerts | No | — | — | — | ✅ Tested |
| 73 | GET | /api/v1/options/chain/{ticker} | No | `ticker` | — | — | ✅ Tested |
| 74 | GET | /users | admin | — | — | — | ✅ Tested |
| 75 | POST | /watchlist/add | No | — | — | `{user_id, ticker, exchange, company_name}` | ✅ Tested |
| 76 | DELETE | /watchlist/remove | No | — | — | `{user_id, ticker}` | ✅ Tested |
| 77 | GET | /watchlist/{user_id} | No | `user_id` | — | — | ✅ Tested |
| 78 | POST | /notifications/register-device | No | — | — | `{user_id, token, platform}` | ✅ Tested |
| 79 | POST | /notifications/test | No | — | — | `{user_id}` | ✅ Tested |
| 80 | POST | /notifications/morning-summary-push | No | — | — | `{user_id}` | ✅ Tested |
| 81 | GET | /api/v1/experts | No | — | — | — | ✅ Tested |
| 82 | GET | /api/v1/expert-posts | No | — | `ticker?` | — | ✅ Tested |
| 83 | GET | /api/v1/dashboard/stream | No | — | — | — | ✅ Tested |
| 84 | GET | /api/v1/market/top-movers | No | — | — | — | ✅ Tested |

---

## Legend

- ✅ Tested — endpoint covered with passing tests
- ⚠️ xfail — endpoint covered but known to return unexpected status codes (bugs tracked in bugs.md)

## Known Issues Summary

| Endpoint | Expected | Actual | Bug Ref |
|----------|----------|--------|---------|
| GET /portfolio/{user_id} | 200 | 500 | BUG-001 |
| GET /portfolio/timeframe-conflicts/{user_id} | 200 (with auth) | 401 | BUG-002 |
| GET /daily-action/{user_id} | 200 (with auth) | 401 | BUG-003 |
