# Morning Briefing — Root Cause Analysis

---

## Why is Morning Briefing not visible?

### Proximate cause
`viewModel.morningBriefData` is populated successfully (API always returns a 200 with either a real brief or fallback), so the card IS rendered. However, the card shows only:

```
• Market data loaded. AI brief unavailable at this time.
```

This is the fallback string, not a real AI brief. From the user's perspective, the feature "doesn't work."

### Root cause chain

```
User opens app
  └── HomeScreen.fetchData(userId)
        └── NetworkManager.getMorningSummary(userId)
              └── GET /morning-summary/{user_id}
                    ├── _dcache_get("morning_brief", user_id) → MISS
                    │     (pregen fired at 2:30 AM IST with correct key,
                    │      but TTL and Redis connection are fine — miss only
                    │      happens if Redis is empty or key expired)
                    └── Live generation fallback
                          └── client.messages.create(..., extra_body={"cache_control": ...})
                                └── Anthropic API → HTTP 400 (bad field)
                                      └── 3 retries × sleep → raises
                                            └── except Exception → return fallback
                                                  └── "AI brief unavailable"
```

**B3 (extra_body Anthropic error)** is the proximate cause of always seeing the fallback text. Even when the pregen succeeds and seeds the cache, users who get a cache miss (e.g., first open, after cache expiry, after portfolio change) see the fallback.

---

## Why is caching not functioning?

Two independent failures compound each other:

### Root cause 1: Invalidation never clears Redis (B1)

```
User buys a stock
  └── POST /portfolio
        └── _cache_invalidate("morning_brief", user_id)
              └── disk_cache.invalidate()
                    └── loop.is_running() == True  (FastAPI is async)
                          └── del _fallback_cache[...] if present
                          └── return  ← NEVER reaches Redis delete
                    └── Redis key: morning_brief:{user_id} still exists
```

The user then opens the app. The stale pregen brief (with old holdings) is returned from Redis cache. The new stock is not mentioned in their morning brief.

### Root cause 2: Scheduler timezone drift causes pregen to fire with stale data (B2)

```
AsyncIOScheduler(timezone="Asia/Dubai")
  └── hour=1, minute=0  →  fires at 01:00 GST = 21:00 UTC = 02:30 AM IST
        └── yfinance.history(period="2d") at 2:30 AM IST
              └── Returns previous trading day's close prices
              └── Market opens at 9:15 AM IST — data is ~19 hours old
```

Even if the brief IS generated and cached, it uses yesterday's close prices from yfinance, not pre-market or live prices.

---

## Why do additional bugs exist?

### B4: Duplicate job — historical code review failure
Copy-paste when registering new jobs; no deduplication check.

### B5: Missing TTL — incomplete API usage
`cache_set` was called without TTL; the namespace-level default silently overrides instead of raising.

### B6: Session over-scoping — architectural debt
The pregen function was written as a monolithic loop without extracting the DB read phase separately from the I/O phase (yfinance, LLM).

### B7: Dead button — incomplete feature
"READ FULL BRIEF" was stubbed during initial UI development and never wired to a destination.

---

## Impact Matrix

| Bug | User Impact | Data Impact | Performance Impact |
|-----|-------------|-------------|-------------------|
| B1 (cache invalidation) | Stale brief after portfolio changes | Incorrect holdings data shown | None |
| B2 (scheduler drift) | Brief generated too early, stale prices | Yesterday's close used | None |
| B3 (extra_body) | Always sees fallback text, never real brief | No AI content | +3s latency on every cache miss |
| B4 (duplicate job) | None visible | Duplicate DB writes | Increased DB load nightly |
| B5 (TTL inconsistency) | Extra LLM calls every 2h if live-gen ran | None | Unnecessary Anthropic cost |
| B6 (session scope) | None visible | None | DB pool starvation during pregen |
| B7 (dead button) | "READ FULL BRIEF" does nothing | None | None |
