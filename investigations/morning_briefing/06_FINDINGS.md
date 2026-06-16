# Morning Briefing — Findings

All conclusions below are proven from source code. No assumptions.

---

## FINDING 1 — Cache Invalidation Is a No-Op in Async Context (CRITICAL)

**File:** `backend/services/disk_cache.py:18-29`

```python
def invalidate(namespace: str, key: str) -> None:
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():          # ← Always True inside FastAPI
        if namespace in cache._fallback_cache and key in cache._fallback_cache[namespace]:
            del cache._fallback_cache[namespace][key]
        return                     # ← Returns here WITHOUT touching Redis
    loop.run_until_complete(cache.invalidate(namespace, key))
```

FastAPI runs every request handler inside an async event loop. `loop.is_running()` is therefore **always True** in the route handlers that call `_cache_invalidate`. The function clears only the per-process in-memory `_fallback_cache` dict and returns early. `cache.invalidate(namespace, key)` — which calls `await r.delete(full_key)` — **is never reached**.

The router calls `_cache_invalidate("morning_brief", str(req.user_id))` in four places (portfolio add, portfolio delete, buy order, sell order). None of them actually clear Redis. The stale pregen brief persists in Redis for the full 24-hour TTL even after the user's holdings change.

---

## FINDING 2 — Scheduler Timezone Drift: Pregen Fires 4 Hours Early (HIGH)

**File:** `backend/services/harvest_worker.py:101`

```python
_scheduler = AsyncIOScheduler(timezone="Asia/Dubai")
```

Dubai is UTC+4. APScheduler interprets all `hour`/`minute` values in the configured timezone. The morning brief pregen is registered as:

```python
_scheduler.add_job(_run_pregen_morning_briefs, "cron", hour=1, minute=0)
# Comment says: "6:30 AM IST (1:00 UTC)"
```

`hour=1, minute=0` in Asia/Dubai (UTC+4) = **01:00 GST = 21:00 UTC prev day = 02:30 AM IST**.

The intent (documented in the comment) was UTC `hour=1` = 1:00 AM UTC = 6:30 AM IST. But the scheduler timezone is Dubai, not UTC. Actual firing time: **2:30 AM IST**, not 6:30 AM IST.

All other jobs have the same drift:
| Job comment | Intended IST | Actual IST |
|-------------|-------------|------------|
| Morning pregen "6:30 AM IST" | 6:30 AM | 2:30 AM |
| Cache purge "3:00 AM IST" | 3:00 AM | 11:00 PM prev |
| Premarket warm "9:00 AM IST" | 9:00 AM | 5:00 AM |
| Error digest "7:00 AM IST" | 7:00 AM | 3:30 AM |

The pregen fires 4 hours before intended, using the previous night's yfinance prices (market closed at 3:30 PM IST).

---

## FINDING 3 — Anthropic `extra_body` Causes Live-Generation Failure (HIGH)

**File:** `backend/routers/portfolio.py:801-806`

```python
response = client.messages.create(
    model=HAIKU_MODEL,
    max_tokens=400,
    messages=[{"role": "user", "content": prompt}],
    extra_body={"cache_control": {"type": "ephemeral"}},  # ← WRONG
)
```

Anthropic prompt caching requires:
1. `extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"}`
2. `cache_control` set **on specific content blocks**, not at the top-level body.

The `extra_body={"cache_control": ...}` sends `cache_control` as a top-level field in the API request JSON. The Anthropic API returns HTTP 400 for unrecognized top-level fields.

The retry loop attempts this 3 times with `time.sleep(1)` and `time.sleep(2)` between attempts (total 3s delay), then re-raises. The outer `except Exception` catches it, writes the fallback to cache, and returns:
```
"• Market data loaded. AI brief unavailable at this time."
```

**Every cache miss triggers a 3-second delay followed by the fallback string.** No real AI brief is ever generated via the live-gen path.

---

## FINDING 4 — Duplicate Scheduler Job Registration (MEDIUM)

**File:** `backend/services/harvest_worker.py:261-262`

```python
_scheduler.add_job(_run_evaluate_analysis_outcomes, "cron", hour=2, minute=0)
_scheduler.add_job(_run_evaluate_analysis_outcomes, "cron", hour=2, minute=0)
```

Identical job registered twice. APScheduler assigns different internal IDs so both fire simultaneously, causing concurrent DB writes and double-processing of analysis outcome rows.

---

## FINDING 5 — Pregen Writes Cache Without Explicit TTL (MEDIUM)

**File:** `backend/services/portfolio_snapshot.py:252`

```python
cache_set(_MORNING_BRIEF_NS, str(user.id), brief)  # No TTL argument
```

`disk_cache.set` → `sync_set(ttl=None)` → `cache_service.CacheService.set` applies `ttl_map.get("morning_brief", 3600)` = **86400s (24 hours)**.

The on-demand live-gen endpoint writes with `_MORNING_CACHE_TTL = 7200` (2 hours):
```python
_dcache_set("morning_brief", str(user_id), result, ttl=_MORNING_CACHE_TTL)
```

If a user opens the app before 6:30 AM (before pregen runs), a live-gen brief is written with a 2h TTL. Two hours later, Redis expires the key. The user opens the app again, triggers another live-gen (3s delay + fallback). This cycle repeats until the pregen overwrites it at 2:30 AM IST with the 24h key.

---

## FINDING 6 — DB Session Held Open Across All yfinance Calls in Pregen (MEDIUM)

**File:** `backend/services/portfolio_snapshot.py:119-258`

```python
with get_session() as db:
    users = db.query(User).all()
    for user in users:
        ...
        for h in holdings:
            t = yf.Ticker(ns_sym)
            hist = t.history(period="2d")   # ← Network call inside session
            ...
        raw = await _deepseek_chat(prompt, max_tokens=600)  # ← LLM call inside session
        cache_set(...)
```

A single DB session context wraps all users, all yfinance HTTP calls (N calls per user), and all DeepSeek LLM calls. If there are 10 users with 5 holdings each, this is one session held open for 50 yfinance fetches + 10 LLM roundtrips. This starves the SQLAlchemy connection pool.

---

## FINDING 7 — iOS "READ FULL BRIEF" Button Has No Action (MEDIUM)

**File:** `ios/StockApp/stockme/stockme/Views/HomeScreen.swift:2724-2735`

```swift
Button {
    HapticManager.selection()   // ← Only action
} label: {
    Text("READ FULL BRIEF")
    ...
}
```

The button fires a haptic but performs no navigation. There is no sheet presentation, no `NavigationStack` push, no state change. Tapping "READ FULL BRIEF" does nothing visible to the user — a dead button.
