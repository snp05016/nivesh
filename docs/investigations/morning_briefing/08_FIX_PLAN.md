# Morning Briefing — Fix Plan

Ordered by impact. Each fix is isolated and safe to apply independently.

---

## FIX 1 — Repair cache invalidation (B1) [CRITICAL]

**File:** `backend/services/disk_cache.py`

**Problem:** `invalidate()` never calls `await r.delete()` in async context.

**Fix:** Replace the broken event-loop detection with `_run_async_in_thread`, identical to how `sync_get`/`sync_set` already work.

```python
def invalidate(namespace: str, key: str) -> None:
    try:
        _run_async_in_thread(cache.invalidate(namespace, key))
    except Exception:
        # Best-effort fallback: clear in-memory only
        if namespace in cache._fallback_cache and key in cache._fallback_cache[namespace]:
            del cache._fallback_cache[namespace][key]
```

**Risk:** Low. `_run_async_in_thread` is already proven in production for `sync_get`/`sync_set`. Thread + new loop pattern sidesteps the running-loop conflict.

---

## FIX 2 — Correct scheduler timezone (B2) [HIGH]

**File:** `backend/services/harvest_worker.py`

**Problem:** `timezone="Asia/Dubai"` causes all cron times to be 4h earlier than intended (all times in comments are UTC-targeting IST).

**Fix:** Change to `timezone="UTC"`. All existing `hour`/`minute` values express UTC, so no other time values need changing.

```python
_scheduler = AsyncIOScheduler(timezone="UTC")
```

**Risk:** Low. All job times in comments confirm UTC intent (e.g., "1:00 UTC → 6:30 AM IST"). Changing timezone to UTC makes the scheduler match its own documentation.

---

## FIX 3 — Remove invalid `extra_body` from Anthropic call (B3) [HIGH]

**File:** `backend/routers/portfolio.py`

**Problem:** `extra_body={"cache_control": {"type": "ephemeral"}}` is rejected by Anthropic API with HTTP 400, causing every live-gen attempt to fail.

**Fix:** Remove `extra_body`. Prompt caching is not needed here (prompt changes per-user anyway).

```python
response = client.messages.create(
    model=HAIKU_MODEL,
    max_tokens=400,
    messages=[{"role": "user", "content": prompt}],
    # extra_body removed
)
```

**Risk:** Zero. Removes a broken parameter. No other behaviour changes.

---

## FIX 4 — Remove duplicate scheduler job (B4) [MEDIUM]

**File:** `backend/services/harvest_worker.py`

**Problem:** `_run_evaluate_analysis_outcomes` added twice.

**Fix:** Delete the second duplicate registration at line 262.

**Risk:** Zero. Removing an exact duplicate.

---

## FIX 5 — Pass explicit TTL in pregen cache write (B5) [MEDIUM]

**File:** `backend/services/portfolio_snapshot.py`

**Problem:** `cache_set(_MORNING_BRIEF_NS, str(user.id), brief)` uses namespace default 86400s instead of the intended 24h explicit value. More importantly, on-demand writes use 7200s, creating a split that causes unnecessary LLM calls.

**Fix:** Set both sides to 86400s (24h) — a morning brief should remain valid for the day.

In `portfolio_snapshot.py`:
```python
cache_set(_MORNING_BRIEF_NS, str(user.id), brief, ttl=86400)
```

In `routers/portfolio.py`, update `_MORNING_CACHE_TTL`:
```python
_MORNING_CACHE_TTL = 86400  # 24h — matches pregen TTL
```

**Risk:** Low. Live-gen briefs persist longer (24h vs 2h), reducing Anthropic calls. Correct behaviour since a brief should remain valid for the day.

---

## FIX 6 — Scope DB session correctly in pregen (B6) [MEDIUM]

**File:** `backend/services/portfolio_snapshot.py`

**Problem:** Single `with get_session() as db:` wraps all I/O (yfinance + LLM) for all users.

**Fix:** Collect all DB data in one scoped session, then release before starting I/O per user.

```python
# Phase 1: DB reads (session scoped tightly)
all_user_data = []
with get_session() as db:
    users = db.query(User).all()
    for user in users:
        holdings = db.query(Portfolio).filter_by(user_id=user.id, group_name="holdings").all()
        if not holdings:
            continue
        tickers = [h.ticker.upper() for h in holdings]
        rows = (db.query(AnalysisHistory)
                .filter(AnalysisHistory.user_id == user.id, AnalysisHistory.ticker.in_(tickers))
                .order_by(AnalysisHistory.created_at.desc()).all())
        last_signals = {}
        for r in rows:
            if r.ticker not in last_signals:
                last_signals[r.ticker] = r.signal
        all_user_data.append((user.id, holdings, last_signals))

# Phase 2: I/O per user (outside session)
for user_id, holdings, last_signals in all_user_data:
    # yfinance + LLM + cache_set here
```

**Risk:** Low. Pattern already used in `snapshot_all_users`. Frees the DB connection during network I/O.

---

## FIX 7 — Wire "READ FULL BRIEF" button (B7) [MEDIUM]

**File:** `ios/StockApp/stockme/stockme/Views/HomeScreen.swift`

**Problem:** "READ FULL BRIEF" button only fires haptic with no navigation action.

**Fix:** When tapped, dismiss the top card (set `morningBriefShownDate = today`) so the full `MorningDecreeCard` scrolls into view. This matches the existing UX intent — `MorningDecreeCard` IS the full brief view.

```swift
Button {
    HapticManager.selection()
    let df = DateFormatter()
    df.dateFormat = "yyyy-MM-dd"
    withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
        morningBriefShownDate = df.string(from: Date())
    }
} label: {
    Text("READ FULL BRIEF")
    ...
}
```

**Risk:** Low. The `MorningDecreeCard` (full brief) was already shown when dismissed — this just makes the "READ FULL BRIEF" button trigger that transition deliberately.

---

## Execution Order

1. Fix 3 (Anthropic `extra_body`) — unblocks live generation immediately
2. Fix 1 (cache invalidation) — ensures portfolio changes propagate
3. Fix 2 (scheduler timezone) — corrects pregen timing going forward
4. Fix 4 (duplicate job) — stops redundant DB work
5. Fix 5 (TTL consistency) — prevents unnecessary LLM calls
6. Fix 6 (DB session scope) — prevents connection pool exhaustion
7. Fix 7 (dead button) — completes iOS UX
