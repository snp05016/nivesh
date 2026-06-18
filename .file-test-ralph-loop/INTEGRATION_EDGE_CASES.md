# Nivesh Integration & Edge Case Analysis

> **Date:** 2026-06-18 | **Scope:** Read-only analysis | **No files modified**

---

## Part 1: API Contract Edge Cases

### 1.1 Empty Responses — `.first()` Without None Checks

**Result: Mostly safe.** Nearly all `.first()` calls are followed by `if not` / `if existing:` guards.

| Endpoint | File:Line | Pattern | Safe? |
|----------|-----------|---------|-------|
| `/batch` POST | `analysis.py:118` | `.first()` → checks `if db_analysis` | ✅ |
| `/portfolio/add` | `portfolio.py:925` | `.first()` → checks `if existing:` → 409 | ✅ |
| `/portfolio/remove` | `portfolio.py:986` | `.first()` → checks `if not holding:` → 404 | ✅ |
| `/portfolio/update` | `portfolio.py:1017` | `.first()` → checks `if not holding:` → 404 | ✅ |
| `/trade-journal/{entry_id}` PUT | `portfolio.py:2461` | `.first()` → checks `if not entry:` → 404 | ✅ |
| `/trade-journal/{entry_id}` DELETE | `portfolio.py:2511` | `.first()` → checks `if not entry:` → 404 | ✅ |
| Net worth ledger | `portfolio.py:2812` | `.first()` → checks `if row is None:` → 404 | ✅ |
| Technical signals | `analysis.py:809` | `.first()` → checks `if not signal:` | ✅ |
| Stock profile (macro) | `market.py:587` | `.first()` → checks `if last:` | ✅ |
| Earnings alerts POST | `market.py:2556` | `.first()` → checks `if existing:` | ✅ |
| Earnings alerts DELETE | `market.py:2595` | `.first()` → checks `if not entry:` | ✅ |
| Signal warnings | `analysis.py:1394` | `.first()` → checks `if not row: continue` | ✅ |
| Signal conflicts | `analysis.py:1431` | `.first()` → checks `if not row or not row.full_json:` | ✅ |
| Alert get | `alerts.py:55` | `.first()` — **returned directly without null guard** | ⚠️ See below |

**⚠️ ISSUE: `alerts.py:55`** — The `.first()` at line 55 is wrapped inside a query building pattern. Need to verify but the `if not`/`raise 404` check on the returned object appears at line 58-59. This is actually safe — the `.first()` result is checked.

### 1.2 Malformed Input — Missing Validation

| Endpoint | File:Line | Issue | Severity |
|----------|-----------|-------|----------|
| `/search` | `market.py:976` | `limit: int = 20` — no validation for negative values | MEDIUM |
| `/trade-journal/{user_id}/stats` | `portfolio.py:2529` | `user_id: int` — no validation for negative/zero | LOW |
| `/api/v1/earnings/alerts/{alert_id}` DELETE | `market.py:2591` | `alert_id: int` — no validation for negative | LOW |
| `/portfolio/update` | `portfolio.py:1007` | Validates `shares > 0`, `buy_price > 0` ✅ | — |
| `/batch` POST | `analysis.py:108` | Validates `len(req.tickers) > 20` ✅ | — |
| `/api/v1/earnings/feed` | `market.py:2227` | `market_cap: str` — no enum validation (accepts any string) | LOW |

**Key gap:** The `search_endpoint` accepts `limit=-100` silently, which would cause downstream slice issues. The `market_cap` parameter on earnings feed accepts any string silently, defaulting to "all" behavior.

### 1.3 Missing Auth — Unprotected Endpoints

| Endpoint | File:Line | Auth? | Risk |
|----------|-----------|-------|------|
| `/api/v1/earnings/alerts` POST | `market.py:2542` | **NONE** | **HIGH** |
| `/api/v1/earnings/alerts/{alert_id}` DELETE | `market.py:2590` | **NONE** | **HIGH** |
| `/trade-journal/{user_id}/stats` | `portfolio.py:2528` | **NONE** | **MEDIUM** |
| `/api/v1/copilot/chat` | `copilot.py:24` | Optional (`get_current_user_id` returns None) | LOW |
| `/healthz` | `health.py:15` | None (public health check, intentional) | — |
| `/search` | `market.py:975` | None (public search, intentional) | — |

**CRITICAL: `earnings_alerts_post_endpoint` and `earnings_alerts_delete_endpoint`** — Anyone can create/delete earnings alerts for any user without authentication. No `verify_access_token` or `require_auth` call exists.

**CRITICAL: `trade_journal_stats_endpoint`** — Any user's trade journal stats are exposed without authentication. Sensitive trading data (PNL patterns, win/loss ratios) is publicly accessible.

**Well-protected endpoints:** Most `portfolio.py` endpoints use `verify_access_token()` then compare with `req.user_id` or `user_id` param. The `require_auth` FastAPI dependency is used for newer endpoints (`stress_test.py`, `correlation.py`, `harvester.py`, `dashboard.py`, `copilot.py`).

### 1.4 Rate Limiting

**No `@limiter` decorator pattern exists in any router.** Rate limiting is done manually via `_check_rate_limit(client_id, endpoint)` calls:

```python
# core/rate_limiter.py — sliding window counters
_RATE_LIMITS = {
    "/analyze": {"window": 3600, "max_requests": 10},
    "/market/quick-info": {"window": 60, "max_requests": 60},
    "/auth/login": {"window": 60, "max_requests": 5},
    "default": {"window": 60, "max_requests": 120}
}
```

| Finding | Detail |
|---------|--------|
| Rate limit headers | ✅ `Retry-After` header set on 429 responses |
| Explicit `_check_rate_limit` calls | Only in `auth.py` (register), `analysis.py` (analyze) — few endpoints actually enforce limits |
| Unprotected high-cost endpoints | `/batch`, `/earnings-calendar`, `/sector-performance`, `/quarterly-financials` — all call yfinance but have no rate guard |
| Memory-only store | Rate limit counters are in-process dicts (`_rate_limit_store`) — lost on restart, not shared across workers |

---

## Part 2: Cache Behavior

### 2.1 TTL Configurations (`config/settings.py`)

| Cache Key | TTL | Env Override |
|-----------|-----|-------------|
| `QUICK_INFO_TTL` | 900s (15 min) | `QUICK_INFO_TTL` |
| `ASM_GSM_CACHE_TTL` | 21,600s (6 hours) | `ASM_GSM_CACHE_TTL` |
| `INDICES_CACHE_TTL` | 300s (5 min) | `INDICES_CACHE_TTL` |
| `MORNING_BRIEF_TTL` | 86,400s (24h) | `MORNING_BRIEF_TTL` |

### 2.2 Cache Invalidation Coverage

| Trigger | Invalidates | File:Line |
|---------|-------------|-----------|
| Portfolio add | `"morning_brief"` for user | `portfolio.py:941` |
| Portfolio remove | `"morning_brief"` for user | `portfolio.py:991` |
| Portfolio update | `"morning_brief"` for user | `portfolio.py:1027` |
| Portfolio note change | `"morning_brief"` for user | `portfolio.py:1078` |
| Admin cache invalidation | Specific ticker analyses | `analysis.py:641-642` |

**NOT invalidated on:**
- Trade journal add/update/delete (could affect stats caching)
- Signal flip events (user would see stale signal on next portfolio load)
- Analysis completion (stale portfolio signal on dashboard until TTL expires)
- Earnings alert creation/deletion (affects dashboard earnings feed)

### 2.3 Cache Stampede Risk

**No request coalescing found.** When a cache key expires (e.g., `morning_brief` at TTL boundary), multiple concurrent requests will all independently:
1. Hit `_dcache_get` → miss
2. Each call yfinance for all holdings
3. Each call the LLM (Anthropic) for the summary
4. Each call `_dcache_set`

This could trigger multiple concurrent LLM calls during peak morning traffic (when Indian market opens), burning credits and overloading the Anthropic API. A `threading.Lock` per cache key or a "promise" pattern would prevent this.

### 2.4 Staleness Logic Bug

**`services/staleness.py:63-64` — Inverted threshold value:**

```python
# CURRENT (BUG: age 3-7 days → +45, but age 8-14 days → +10)
if age_days > 30:
    score += 40       # >30 days = +40
elif age_days > 14:
    score += 25       # 15-30 days = +25
elif age_days > 7:
    score += 10       # 8-14 days = +10
elif age_days > 2:
    score += 45       # ⚠️ 3-7 days = +45 (HIGHER than 8-14d!)
```

This causes analyses 3-7 days old to be scored as STALE (45+) while 8-14 day old analyses are only AGING (10). The value `45` appears to be a typo for `5`. The resulting behavior:
- Day 3-7 after analysis: **STALE** (score 45+) — triggers full multi-agent re-analysis
- Day 8-14: **AGING** (score 10+) — less urgent than day 3-7

This is illogical: staleness should increase monotonically with age.

---

## Part 3: Error Recovery

### 3.1 Try/Except Patterns

**✅ No bare `except:` blocks found anywhere in services/ or routers/.** All exception handling uses at least `except Exception:`.

**⚠️ Silent swallowing patterns exist but are intentional:**

| File | Pattern | Assessment |
|------|---------|------------|
| `analysis.py:387-390` | `except Exception: pass` | Non-critical enrichment; safe to swallow |
| `analysis.py:1418` | `except Exception: pass` | Signal warning enrichment; safe |
| `analysis.py:1447-1448` | `except Exception: pass` | Conflict detection in loop; safe |
| `market.py:597-600` | `except Exception: pass` | AI summary enrichment; safe |
| `portfolio.py:2469-2470` | `except Exception: pass` | Trade journal mood update; borderline — should at least log |

### 3.2 Multiprocessing Cleanup

**Proper cleanup confirmed:**

| File:Line | Pattern | Status |
|-----------|---------|--------|
| `copilot_service.py:147` | `p.terminate()` on timeout | ✅ |
| `job_manager.py:44` | `p.terminate()` on cancel | ✅ |
| `job_manager.py:47` | `p.kill()` fallback after terminate | ✅ |
| `analysis.py:140-175` | Worker catches exceptions → puts error in queue | ✅ |
| `analysis.py:140-175` | Subprocess re-imports deps + `load_dotenv(override=True)` | ✅ |

### 3.3 DB Session Rollback

**Main `database.py:get_session()`:**

```python
try:
    yield session
except Exception:
    session.rollback()
    raise
finally:
    session.close()
```

✅ Proper rollback on exception. Does NOT auto-commit on success (caller must `session.commit()`).

**⚠️ `harvester_db.py:get_session()` has DIFFERENT behavior:**

```python
try:
    yield session
    session.commit()    # AUTO-COMMITS on success
except Exception:
    session.rollback()
    raise
finally:
    session.close()
```

This is an **auto-commit** session. Any service mixing both session managers could see unexpected commits. The two `get_session()` implementations have different semantics — this is architectural drift.

### 3.4 `sector_rotation.py:75` — `datetime.now()` Without Timezone

```python
end_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
```

This uses local time without timezone awareness. On the server, this may differ from IST, causing the "7 days ago" calculation to drift by hours. Same pattern at `microstructure_engine.py:105`, `portfolio.py:275,278`.

---

## Part 4: Dawn Bug Check

### 4.1 Midnight / Date Boundaries

| Issue | Location | Risk |
|-------|----------|------|
| **UAE offset instead of IST** | `staleness.py:10` | MEDIUM |
| **Inconsistent timezone in staleness** | `staleness.py:48` (no tz) vs `:52` (UAE) | MEDIUM |
| **`date.today()` for analysis_date** | `analysis_repo.py:57` | MEDIUM |

**Detail:** `staleness.py` uses `UAE_OFFSET = timedelta(hours=4)` (UTC+4) for all timestamp comparisons, but Indian markets operate on IST (UTC+5:30). The 1:30 hour difference means:
- At 23:30 IST, the staleness checker considers it the next day (UAE midnight passed)
- Pre-market detection (`is_pre_market()`) uses 09:15 IST but compares against UAE-time `now_uae`
- The age calculation at line 53 uses UAE offset, so "3 days old" calculations are off by 1.5 hours relative to India

**`date.today()` risk:** `analysis_repo.py:57` sets `analysis_date=date.today().isoformat()`. If the server runs at midnight IST (18:30 UTC previous day), this creates the wrong date for IST market days. Should use `datetime.now(timezone.utc) + IST_OFFSET` then take `.date()`.

### 4.2 Month End — Portfolio Snapshots

`portfolio_snapshot.py` takes daily snapshots via `snapshot_all_users()` but:
- No month-end aggregation (e.g., computing monthly returns)
- No handling of month-end corporate actions (bonus, splits, dividend records) that would affect NAV
- If `snapshot_all_users()` fails mid-loop (server restart), some users get snapshots and others don't for that day — no idempotency beyond the `existing` check

### 4.3 Weekend / Market Closed

| Area | Handling | Status |
|------|----------|--------|
| Board meeting filings | `_expand_weekend_window()` expands Sat→Fri, Sun→Fri+Mon | ✅ |
| Price fetching | All yfinance calls proceed regardless of day — returns last close | ⚠️ |
| Staleness scoring | No weekend awareness — analyses age through weekends at same rate | ⚠️ |
| Morning brief generation | Scheduled at 6:30 AM IST regardless of weekday | ⚠️ |

**Weekend risk:** On Saturday/Sunday, yfinance `t.history(period="2d")` returns Friday's close. All price-dependent calculations (PNL, day change, staleness) use this stale price without flagging it as "market closed." The morning brief would contain Friday's data labeled as "today."

### 4.4 Empty Database (Fresh Install)

| Scenario | Handling | Status |
|----------|----------|--------|
| DB seeding | `init_db()` creates 3 users + 16 holdings for nirav | ✅ |
| Empty AnalysisHistory | `get_last_analysis_any_type()` returns None | ✅ |
| Empty Portfolio | `portfolio_endpoint` returns empty sections | ✅ |
| Empty NetWorthLedger | Returns 404 with helpful message | ✅ |
| Empty TradeJournal | `trade_journal_stats_endpoint` returns zeros | ✅ |
| Empty EarningsAlert | `earnings_alerts_get_endpoint` returns empty list | ✅ |

### 4.5 `datetime.utcnow` — Forbidden per AGENTS.md §3.5

| File:Line | Usage | Risk |
|-----------|-------|------|
| `harvester_db.py:82` | `Column(DateTime, default=datetime.utcnow)` | MEDIUM |
| `harvester_db.py:124` | `Column(DateTime, default=datetime.utcnow)` | MEDIUM |
| `filings_extractor.py:251` | `_dt.utcnow().year` | LOW |

**AGENTS.md §3.5 requires:** `default=lambda: datetime.now(timezone.utc)` — evaluated at row-insert time, not import time. The `datetime.utcnow` approach captures the import-time timestamp once, so all rows get the same default value.

---

## Summary: Risk Matrix

| Category | Issue | Severity | Blast Radius |
|----------|-------|----------|-------------|
| Auth | Unprotected earnings alerts CRUD | **CRITICAL** | Data integrity for all users |
| Auth | Unprotected trade journal stats | **HIGH** | Privacy — exposes trading patterns |
| Rate limit | No rate limiting on yfinance-calling endpoints | **HIGH** | API cost + DoS risk |
| Cache bug | Staleness scoring inversion (age 3-7 > age 8-14) | **HIGH** | Wastes AI credits on unnecessary re-analysis |
| Cache | No cache stampede protection | **MEDIUM** | Multiple concurrent LLM calls on TTL expiry |
| Timezone | UAE offset instead of IST in staleness | **MEDIUM** | Incorrect staleness scores near midnight |
| Timezone | `date.today()` used for DB analysis_date | **MEDIUM** | Wrong date at midnight boundary |
| Timezone | `datetime.now()` without tz in sector_rotation | **LOW** | Drift in 7-day lookback |
| DB model | `datetime.utcnow` in harvester_db models | **MEDIUM** | Import-time default for all rows |
| DB session | Inconsistent auto-commit behavior in harvester_db | **MEDIUM** | Architectural drift, unexpected commits |
| Input | No validation on negative query params | **LOW** | Minor errors, no data corruption |
| Weekend | Market-closed days not handled | **LOW** | Stale data shown without indicator |
| Month-end | No month-end aggregation or special handling | **LOW** | Missing monthly performance views |
