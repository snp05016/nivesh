# Nivesh — API Reference

> Source of truth: actual router files in `backend/routers/`.
> Base URL (production): `https://api.nivesh.qzz.io`
> All endpoints require `Authorization: Bearer <JWT>` unless marked *public*.
> Endpoints marked with 🔄 spawn a `multiprocessing.Process` for heavy computation.

---

## Health

### `health.py`

| Method | Path | Description | Notes |
|--------|------|-------------|-------|
| `GET` | `/ping` | Zero-dependency liveness probe — no DB, no yfinance | Public |
| `GET` | `/healthz` | DB-backed health check — verifies DB connectivity | Public |

---

## Authentication

### `auth.py`

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/register` | Create a new user account (username, password, display_name) |
| `POST` | `/login` | Authenticate and receive a JWT access token |
| `POST` | `/refresh` | Refresh an expired JWT token |

---

## Analysis

### `analysis.py`

| Method | Path | Description | Notes |
|--------|------|-------------|-------|
| `POST` | `/analyze` | Submit stock for AI analysis (v2 async — returns job_id) | 🔄 |
| `GET` | `/analyze/status/{job_id}` | Poll analysis job status (QUEUED/RUNNING/DONE/FAILED) | |
| `GET` | `/analyze/stream/{job_id}` | SSE stream: live progress stages during analysis | |
| `GET` | `/analyze/result/{job_id}` | Retrieve completed analysis JSON | |
| `POST` | `/analyze/batch` | Submit multiple tickers for batch analysis | 🔄 |
| `GET` | `/analysis/history` | Get authenticated user's analysis history | |
| `GET` | `/analysis/{ticker}` | Get most recent cached analysis for ticker | |
| `DELETE` | `/analysis/{id}` | Delete an analysis history record | |
| `GET` | `/morning-brief` | AI-generated morning market brief | 🔄 |
| `GET` | `/signals` | Aggregated recent buy/sell signals across universe | |
| `GET` | `/screener` | Fundamental screener (P/E, market cap, sector filters) | |

---

## Market Data

### `market.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/market/indices` | Nifty 50, Sensex, Bank Nifty, and other major indices |
| `GET` | `/market/nifty-history` | Historical OHLCV data for Nifty 50 |
| `GET` | `/market/option-chain/{ticker}` | NSE option chain for a stock or index |
| `GET` | `/market/sector-pe` | Sector-wise P/E ratios |
| `GET` | `/market/institutional-flow` | FII/DII net buy/sell data |
| `GET` | `/market/bulk-deals` | Recent bulk and block deals on NSE/BSE |
| `GET` | `/market/filings/{ticker}` | SEBI corporate filings for a company |
| `GET` | `/market/stock-info/{ticker}` | Quick stock info: price, 52w high/low, market cap |
| `GET` | `/market/nse-directory` | Full NSE stock directory (628+ tickers) |
| `GET` | `/market/sector-stocks` | Stocks grouped by sector |
| `GET` | `/market/block-deals` | Block deals data |
| `GET` | `/market/macro-events` | Macro events calendar |
| `GET` | `/market/earnings-calendar` | Upcoming earnings dates |
| `GET` | `/market/ipo-pipeline` | Upcoming IPO listings |
| `GET` | `/market/mutualfund-nav` | AMFI mutual fund NAV data |

---

## Portfolio

### `portfolio.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/portfolio` | Get authenticated user's holdings |
| `POST` | `/portfolio` | Add a holding to portfolio |
| `PUT` | `/portfolio/{id}` | Update holding (shares, buy_price, notes) |
| `DELETE` | `/portfolio/{id}` | Remove a holding |
| `GET` | `/portfolio/performance` | P&L, CAGR, absolute return vs Nifty benchmark |
| `GET` | `/portfolio/networth` | Current net worth (holdings + cash) |
| `GET` | `/portfolio/networth/history` | Net worth over time (snapshots) |
| `GET` | `/portfolio/charts/{period}` | Performance chart data (1D/1W/1M/1Y/ALL) |
| `POST` | `/portfolio/export/xlsx` | Export portfolio as Excel file |
| `POST` | `/portfolio/export/pdf` | Export portfolio as PDF report |
| `GET` | `/portfolio/watchlist` | Get user's watchlist |
| `POST` | `/portfolio/watchlist` | Add ticker to watchlist |
| `DELETE` | `/portfolio/watchlist/{ticker}` | Remove from watchlist |
| `GET` | `/portfolio/trade-journal` | Trade journal entries |
| `POST` | `/portfolio/trade-journal` | Log a trade journal entry |
| `PUT` | `/portfolio/trade-journal/{id}` | Update trade journal entry |
| `DELETE` | `/portfolio/trade-journal/{id}` | Delete trade journal entry |

---

## Alerts

### `alerts.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/alerts` | Get all price alerts for authenticated user |
| `POST` | `/alerts` | Create a price alert (ticker, target price, direction) |
| `PUT` | `/alerts/{id}` | Update alert threshold |
| `DELETE` | `/alerts/{id}` | Delete a price alert |
| `GET` | `/alerts/active` | Get alerts currently triggered/firing |

---

## User

### `user.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/user/profile` | Get authenticated user's profile |
| `PUT` | `/user/profile` | Update display name or preferences |
| `PUT` | `/user/password` | Change password |
| `GET` | `/user/admin/users` | List all users (admin only) |
| `POST` | `/user/admin/promote` | Promote user to admin role |
| `GET` | `/user/settings` | Get user notification and app settings |
| `PUT` | `/user/settings` | Update user settings |

---

## Notifications

### `notifications.py`

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/notifications/register` | Register device APNs token |
| `DELETE` | `/notifications/unregister` | Remove device token |
| `POST` | `/notifications/send` | Send push notification (admin only) |
| `GET` | `/notifications/history` | Past push notification history |

---

## Harvester (Content Ingestion)

### `harvester.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/content/feed` | Paginated content feed (news, videos, filings) |
| `GET` | `/content/governance/{ticker}` | Governance data for a company |
| `GET` | `/content/search` | Full-text search across harvested content |
| `POST` | `/harvest/trigger/youtube` | Manually trigger YouTube harvest (admin) |
| `POST` | `/harvest/trigger/news` | Manually trigger news harvest (admin) |
| `POST` | `/harvest/trigger/filings` | Manually trigger SEBI filings harvest (admin) |
| `GET` | `/harvest/status` | Current harvest job status for all sources |

---

## Dashboard

### `dashboard.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/dashboard` | Serve admin HTML dashboard (Chart.js) |
| `GET` | `/dashboard-data` | JSON: active jobs, completed jobs, request log, token stats |

---

## Stress Test

### `stress_test.py`

| Method | Path | Description | Notes |
|--------|------|-------------|-------|
| `POST` | `/stress-test` | Run 14-scenario portfolio stress test | 🔄 |
| `GET` | `/stress-test/status/{job_id}` | Poll stress test job status | |
| `GET` | `/stress-test/result/{job_id}` | Retrieve stress test results | |

---

## Correlation

### `correlation.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/correlation` | Compute portfolio correlation matrix and diversification score |
| `GET` | `/correlation/sector` | 11-sector proxy correlation matrix |

---

## Sector Rotation

### `sector_rotation.py` (prefix: `/api/v1`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/sector-rotation` | Multi-period sector quadrant (1m/3m/6m/1y) with FII/DII flow |
| `GET` | `/api/v1/sector-rotation/momentum` | Sector momentum ranking |

---

## Earnings Surprise

### `earnings_surprise.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/earnings-surprise` | Recent EPS surprises across the universe |
| `GET` | `/earnings-surprise/{ticker}` | Historical EPS surprise pattern for a stock |
| `GET` | `/earnings-surprise/{ticker}/impact` | Post-earnings price impact (1d/5d) |

---

## Natural Language Screener

### `nl_screener.py`

| Method | Path | Description | Notes |
|--------|------|-------------|-------|
| `POST` | `/nl-screener` | Natural language query -> SQL -> filtered stock results | 🔄 |

---

## Options Strategy

### `options_strategy.py`

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/options/strategy` | Compute multi-leg options payoff (CALL/PUT x LONG/SHORT) |
| `GET` | `/options/chain/{ticker}` | Live option chain for a ticker |

---

## Market Anomalies

### `anomalies.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/anomalies` | Recent market anomalies with severity classification |

---

## Brainstorming

### `brainstorming.py`

| Method | Path | Description | Notes |
|--------|------|-------------|-------|
| `POST` | `/brainstorm` | AI-generated investment idea generation | 🔄 |

---

## Copilot

### `copilot.py`

| Method | Path | Description | Notes |
|--------|------|-------------|-------|
| `POST` | `/copilot/chat` | Conversational AI stock market message | 🔄 |
| `GET` | `/copilot/history` | Copilot conversation history |
| `DELETE` | `/copilot/history` | Clear copilot conversation history |

---

## Strategy (Backtest)

### `strategy.py`

| Method | Path | Description | Notes |
|--------|------|-------------|-------|
| `POST` | `/strategy/backtest` | Backtest a trading strategy | 🔄 |

---

## ML Engine API

Base URL: `http://localhost:8001` (or configured via `ML_ENGINE_URL` env var)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe — confirms LightGBM + TRA models are loaded |
| `POST` | `/predict/cross-section` | Batch cross-sectional predictions for multiple stocks; body: list of `{ticker, ohlcv_data}` |
| `POST` | `/predict/single` | Single-stock prediction from OHLCV data; returns `expected_direction` (-1/0/+1) and `confidence_score` (0.0-1.0) |
| `GET` | `/model/status` | Loaded model metadata: paths, feature count, load timestamp |

### POST /predict/single — Request Body

```json
{
  "ticker": "RELIANCE",
  "ohlcv_data": [
    { "open": 2450.0, "high": 2470.0, "low": 2430.0, "close": 2460.0, "volume": 5000000 }
  ]
}
```

### POST /predict/single — Response

```json
{
  "ticker": "RELIANCE",
  "expected_direction": 1,
  "confidence_score": 0.72,
  "feature_count": 158,
  "ml_engine_mode": "lgbm_trained"
}
```

---

## Standard Response Conventions

- All analysis responses pass through `_normalize_response()` and `_ban_western_scale()` before returning to the client.
- Monetary values are always in Lakhs/Crores (never Millions/Billions).
- AI-generated text fields are stripped of emoji via `stripEmoji()` on the iOS side.
- Error responses use standard FastAPI HTTP error format: `{"detail": "message"}`.
- Rate limit responses: `429 Too Many Requests` with `Retry-After` header.

---

## Authentication Details

```
Header: Authorization: Bearer <jwt_token>
Token lifetime: configurable via JWT_EXPIRE_MINUTES env var
```

JWT tokens are issued by `POST /login` and verified by `core/security.py:get_current_user_id()`.
