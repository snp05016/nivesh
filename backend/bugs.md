# Bug Tracking Ledger

## Unfixed Bugs (Pending Review/Action)

[Bug-001] - [.env / Anthropic Dashboard] - CRITICAL - The `.env` file contains a live Anthropic API key that must be rotated on Anthropic's dashboard. The key was never committed to git history (verified: `git log --all -- .env` returns empty). Action required: log into console.anthropic.com, revoke the current key, generate a new one, and update `.env` on both local and server.

---

## Fixed Bugs (Applied Fixes)

[Bug-002] - [database.py + main.py / Authentication] - CRITICAL - No JWT/session authentication existed. All API endpoints were unauthenticated. Fixed: implemented full JWT auth system — `create_access_token()`, `verify_access_token()`, `require_auth()`, `require_admin()` in `database.py`. Updated `/login` to return `access_token`. Protected all user-scoped endpoints (portfolio, watchlist, alerts, trade-journal, morning-summary, risk-analysis, red-flags, macro-impact, timeframe-conflicts, valuation-history, export/excel, export/pdf, daily-action, signal-warnings). Protected admin endpoints (dashboard-data, token-stats) with `require_admin()`. Added `promote_initial_admins()` on startup.

[Bug-003] - [main.py / CORS] - HIGH - CORS defaulted to `allow_origins=["*"]`. Fixed: changed default to `"http://localhost:3000,http://127.0.0.1:3000"`.

[Bug-004] - [main.py / /analyze] - HIGH - No per-user concurrency limit on expensive AI operations. Fixed: added per-user `threading.Semaphore` (`_ANALYZE_MAX_CONCURRENT = 2`). Each `/analyze` call acquires the semaphore; returns 429 if limit reached. Semaphore released in `finally` block.

[Bug-005] - [main.py / /dashboard-data] - HIGH - Admin dashboard exposed without authentication. Fixed: added `require_admin(authorization)` dependency.

[Bug-006] - [main.py / /token-stats] - HIGH - Token usage/cost data exposed without authentication. Fixed: added `require_admin(authorization)` dependency.

[Bug-007] - [database.py / Password Hashing] - HIGH - Used SHA-256 (fast, GPU-vulnerable). Fixed: migrated to `bcrypt` with `rounds=12`. Backward-compatible: `verify_password()` detects old `salt:hash` format and falls back to SHA-256 comparison.

[Bug-008] - [main.py / /register] - MEDIUM - No rate limiting on registration. Fixed: added IP-based rate limiting to `/register` endpoint.

[Bug-009] - [main.py / /analyze subprocess] - MEDIUM - `p.terminate()` + `p.join()` without timeout could hang. Fixed: added `p.join(timeout=5)` then `p.kill()` + `p.join(timeout=2)` for forced cleanup.

[Bug-010] - [services/scraper.py / Cache] - MEDIUM - Unbounded dict cache. Fixed: replaced with `OrderedDict` LRU cache with `_CACHE_MAX_SIZE = 50`. Evicts least-recently-used entries when full.

[Bug-011] - [services/advisor_harvester.py / _load_env()] - MEDIUM - `_load_env()` called at module import time (side effect). Fixed: moved to `harvest_all_advisors()` function body, called at CRON execution time only.

[Bug-012] - [main.py / /health] - MEDIUM - Exposed `anthropic_key_set` boolean to public. Fixed: removed from response body; kept as internal variable for status calculation only.

[Bug-013] - [services/news_harvester.py / Transactions] - MEDIUM - Single transaction for entire harvest loop. Fixed: added `db.begin_nested()` savepoints per article. Each article commits or rolls back independently.

[Bug-014] - [services/pkscreener_runner.py / subprocess] - MEDIUM - Used `"python"` which may resolve to wrong interpreter. Fixed: changed to `sys.executable`.

[Bug-015] - [main.py / /screener] - LOW - No circuit breaker for yfinance failures. Fixed: added `_yf_circuit_*` state machine (3 failures → open for 5 minutes → half-open retry).

[Bug-016] - [main.py / /morning-summary] - LOW - AI failure fallback already existed (line 1991-1996). Verified: fallback dict is returned on any exception. No fix needed.

[Bug-017] - [iOS / HomeScreen.swift] - LOW - Pull-to-refresh did not refresh home feed. Fixed: added `feedVM.fetch(userId: user.userId, forceRefresh: true)` in `.refreshable` block.

[Bug-018] - [database.py / SQLite WAL] - SQLite missing `PRAGMA busy_timeout=5000`. Fixed: added to `_set_sqlite_wal` event listener.

[Bug-019] - [main.py / Security Headers] - No security headers. Fixed: added `_SecurityHeadersMiddleware` (nosniff, DENY, XSS protection, referrer policy).

[Bug-020] - [main.py / Rate Limiting] - No rate limiting. Fixed: added in-memory rate limiter (30 req/60s per IP).

[Bug-021] - [main.py / Input Validation] - No ticker/exchange validation. Fixed: added `@validator("ticker")` regex and `@validator("exchange")` whitelist.

[Bug-022] - [services/news_harvester.py / Date Parsing] - RSS date parsing could crash. Fixed: wrapped in try/except with fallback.

[Bug-023] - [services/scraper.py / Division by Zero] - `breadth_ratio` division by zero. Fixed: added zero check.

[Bug-024-028] - [services/* / DB Session Management] - 5 service files used manual session management. Fixed: all migrated to `get_session()` context manager.

[Bug-029] - [iOS / HomeFeedViewModel.swift / Race Condition] - No task cancellation. Fixed: added `fetchTask` with cancellation and `guard !Task.isCancelled`.

[Bug-030] - [tests/test_e2e_api.py] - No integration tests. Created 50+ E2E tests.

---

## Pytest Test Suite — Known API Issues (discovered 2026-06-04)

- [ ] GET /portfolio/{user_id} — 500 on valid user_id — discovered in `TestPortfolioGet::test_portfolio_get_valid_user_returns_200`
- [ ] GET /portfolio/timeframe-conflicts/{user_id} — 401 even with valid auth token — discovered in `TestTimeframeConflicts::test_timeframe_conflicts_authenticated_returns_200`
- [ ] GET /daily-action/{user_id} — 401 even with valid auth token — discovered in `TestDailyAction::test_daily_action_authenticated_returns_200`

### BUG-031: GET /portfolio/{user_id} returns 500

**Severity:** High — core feature broken  
**Symptom:** Endpoint returns HTTP 500 for a valid, seeded user_id that has portfolio entries.  
**Hypothesis:** The portfolio router calls `_yf_price` or similar for each holding to compute current market value. When yfinance fails (rate limit, timeout, or mocked in test env), the exception propagates as an unhandled 500.  
**Fix suggestion:** Wrap each external price fetch in a try/except and fall back to the stored `buy_price` so the endpoint degrades gracefully instead of crashing.

### BUG-032: GET /portfolio/timeframe-conflicts/{user_id} returns 401 with valid token

**Severity:** Medium — feature inaccessible despite correct credentials  
**Symptom:** Endpoint validates the JWT token but then returns 401.  
**Hypothesis:** The inline token check compares `token_user_id != path_user_id` but `verify_access_token` may return a string while the path param is an int, causing the equality check to always fail.  
**Fix suggestion:** Ensure `verify_access_token` returns `int`. Consider returning 403 (Forbidden) rather than 401 when the token is valid but user_id doesn't match.

### BUG-033: GET /daily-action/{user_id} returns 401 with valid token

**Severity:** Medium — feature inaccessible despite correct credentials  
**Symptom:** Same pattern as BUG-032 — valid Bearer token from login is rejected.  
**Hypothesis:** Same root cause — string vs int mismatch in the path param / token user_id comparison. Both `daily-action` and `timeframe-conflicts` share this pattern, suggesting a systemic issue in how auth-required endpoints compare the decoded user_id.  
**Fix suggestion:** Centralise auth+user_id comparison in a single `require_auth_for_user(user_id, authorization)` helper to avoid per-endpoint drift. Cast both sides to `int` before comparing.

### Reproduction Steps

```bash
# Register and login
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"username":"bugtest","password":"Test1234!","display_name":"Bug Test"}'

TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"bugtest","password":"Test1234!"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['access_token']); open('/tmp/uid','w').write(str(d['user_id']))")
UID=$(cat /tmp/uid)

# BUG-031: Portfolio 500
curl http://localhost:8000/portfolio/$UID

# BUG-032: Timeframe conflicts 401
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/portfolio/timeframe-conflicts/$UID

# BUG-033: Daily action 401
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/daily-action/$UID
```
