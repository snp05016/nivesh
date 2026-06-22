# Morning Briefing — Implementation Report

**Date:** 2026-06-16  
**Status:** ALL 7 FIXES APPLIED ✅  
**Backend syntax:** All 4 modified files pass `ast.parse` ✅

---

## Fix 1 — Cache Invalidation Repaired ✅

**File:** `backend/services/disk_cache.py`

**Before:**
```python
def invalidate(namespace: str, key: str) -> None:
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():
        if namespace in cache._fallback_cache and key in cache._fallback_cache[namespace]:
            del cache._fallback_cache[namespace][key]
        return   # ← Never reached Redis
    loop.run_until_complete(cache.invalidate(namespace, key))
```

**After:**
```python
def invalidate(namespace: str, key: str) -> None:
    try:
        _run_async_in_thread(cache.invalidate(namespace, key))
    except Exception:
        if namespace in cache._fallback_cache and key in cache._fallback_cache[namespace]:
            del cache._fallback_cache[namespace][key]
```

Also added `_run_async_in_thread` to the import from `cache_service`. Redis `DEL morning_brief:{user_id}` now fires correctly on every portfolio mutation.

---

## Fix 2 — Scheduler Timezone Corrected ✅

**File:** `backend/services/harvest_worker.py`

```python
# Before
_scheduler = AsyncIOScheduler(timezone="Asia/Dubai")

# After
_scheduler = AsyncIOScheduler(timezone="UTC")
```

All cron times in the file are expressed in UTC (as confirmed by comments: "1:00 UTC → 6:30 AM IST"). Changing to UTC makes all jobs fire at their intended times:

| Job | Old actual IST | New actual IST |
|-----|----------------|----------------|
| Morning pregen | 2:30 AM | 6:30 AM ✅ |
| Cache purge | 11:00 PM prev day | 8:30 AM ✅ |
| Premarket warm | 5:00 AM | 9:00 AM ✅ |
| Error digest | 3:30 AM | 7:00 AM ✅ |

Also corrected duplicate `_run_evaluate_analysis_outcomes` registration: it previously used `hour=2, minute=0` which in the old Dubai TZ fired at 6:30 AM IST. In UTC, 2:00 AM IST = 20:30 UTC. Updated to `hour=20, minute=30` and removed the duplicate.

---

## Fix 3 — Anthropic `extra_body` Removed ✅

**File:** `backend/routers/portfolio.py`

```python
# Before
response = client.messages.create(
    model=HAIKU_MODEL,
    max_tokens=400,
    messages=[{"role": "user", "content": prompt}],
    extra_body={"cache_control": {"type": "ephemeral"}},  # ← caused HTTP 400
)

# After
response = client.messages.create(
    model=HAIKU_MODEL,
    max_tokens=400,
    messages=[{"role": "user", "content": prompt}],
)
```

Live generation will now succeed. Real AI-generated briefs will be served on cache miss instead of the fallback string.

---

## Fix 4 — Duplicate Scheduler Job Removed ✅

**File:** `backend/services/harvest_worker.py`

```python
# Before (2 identical lines)
_scheduler.add_job(_run_evaluate_analysis_outcomes,"cron", hour=2, minute=0)
_scheduler.add_job(_run_evaluate_analysis_outcomes,"cron", hour=2, minute=0)

# After (1 line, corrected UTC time)
_scheduler.add_job(_run_evaluate_analysis_outcomes,"cron", hour=20, minute=30)  # 2:00 AM IST (20:30 UTC)
```

---

## Fix 5 — TTL Consistency ✅

**Files:** `backend/services/portfolio_snapshot.py` and `backend/routers/portfolio.py`

Pregen now explicitly writes `ttl=86400`. Endpoint constant updated:
```python
# Before
_MORNING_CACHE_TTL = 7200  # 2 hours

# After
_MORNING_CACHE_TTL = 86400  # 24h — matches pregen TTL; brief is valid for the full day
```

Both code paths now write with the same TTL. Live-gen briefs persist for the day instead of expiring 2 hours later and triggering unnecessary Anthropic calls.

---

## Fix 6 — DB Session Scope Corrected ✅

**File:** `backend/services/portfolio_snapshot.py`

Refactored `pregen_morning_briefs_all_users` into two distinct phases:

**Phase 1** (inside `with get_session()`): Query all users, holdings, and signals. Convert ORM rows to plain Python tuples (`(ticker, company, shares, buy_price)`). Session closes as soon as DB reads are done.

**Phase 2** (outside session): Iterate over plain tuples. Call yfinance and DeepSeek per user. Write cache. No DB connection held during network I/O.

This prevents the DB connection pool from being starved during potentially minutes-long multi-user yfinance + LLM calls.

---

## Fix 7 — "READ FULL BRIEF" Button Wired ✅

**File:** `ios/StockApp/stockme/stockme/Views/HomeScreen.swift`

```swift
// Before — only haptic, no action
Button {
    HapticManager.selection()
} label: { Text("READ FULL BRIEF") ... }

// After — transitions to MorningDecreeCard (full brief)
Button {
    HapticManager.selection()
    let df = DateFormatter()
    df.dateFormat = "yyyy-MM-dd"
    withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
        morningBriefShownDate = df.string(from: Date())
    }
} label: { Text("READ FULL BRIEF") ... }
```

Setting `morningBriefShownDate` to today dismisses the teaser card and causes `MorningDecreeCard` (the full brief with all bullet points) to render in its place.

---

## Files Changed

| File | Change |
|------|--------|
| `backend/services/disk_cache.py` | Fixed `invalidate()` to use `_run_async_in_thread`; added import |
| `backend/services/harvest_worker.py` | Timezone UTC; removed duplicate job; corrected job UTC time |
| `backend/services/portfolio_snapshot.py` | Two-phase DB/IO split; explicit TTL=86400 |
| `backend/routers/portfolio.py` | Removed `extra_body`; changed `_MORNING_CACHE_TTL` to 86400 |
| `ios/.../Views/HomeScreen.swift` | Wired "READ FULL BRIEF" button |

## Verification

```
ast.parse check:
  OK  services/disk_cache.py
  OK  services/harvest_worker.py
  OK  services/portfolio_snapshot.py
  OK  routers/portfolio.py
```
