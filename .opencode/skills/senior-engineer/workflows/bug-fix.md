# Bug Fix Workflow

Fix bugs methodically. Never guess. Reproduce → isolate → fix → verify.

## Checklist

### 1. Reproduce
- Reproduce the bug via API call, log check, or code path trace.
- Confirm it's real — not a stale report, not a misunderstanding.
- If can't reproduce → report that and stop.

### 2. Isolate
- Find the root cause by reading the relevant code path.
- Check: router → service → repository → DB model.
- For iOS: view → view model → NetworkManager → API.
- Look at git blame for recent changes to the affected files.

### 3. Fix
- Apply the SMALLEST fix that resolves the root cause.
- Do not refactor adjacent code.
- Do not add logging "for next time" unless the user asks.
- One bug = one fix. Do not chain unrelated fixes in same commit.

### 4. Add Regression Test
- If tests are permitted (backend tests remote-only per AGENTS.md §6.5):
  - Add a test that FAILS before the fix, PASSES after.
  - For iOS: verify Swift source doesn't have compile errors.
- If tests are forbidden in this context → document "test skipped per AGENTS.md §6.5"

### 5. Verify
- Re-test the original reproduction steps.
- Run any existing tests in the affected area.
- For server-side fixes: deploy and verify on production.

### 6. Report
```
**Root cause**: <one-line explanation>
**Fix**: <one-line explanation>
**Files changed**: <list>
**Tests**: <results or skipped reason>
**Deployment**: <SHA, health status if applicable>
```

## Anti-Patterns

- ❌ Fixing a bug by adding a try/catch that swallows the error
- ❌ Fixing by adding a null check without understanding why it was null
- ❌ Fixing 3 bugs in one commit ("while I'm here")
- ❌ Adding a `print()` instead of proper error handling
- ❌ Changing the architecture to fix a typo

## Example

```
User: "dividends endpoint returns 500"

1. Reproduce: curl /dividends/RELIANCE.NS → 500
2. Isolate: t.calendar returns dict in newer yfinance, .empty attribute doesn't exist
3. Fix: add hasattr(cal, "empty") check with dict fallback
4. Test: remote pytest test_dividends (skipped per §6.5 — no local backend tests)
5. Verify: curl → 200, 8 dividend entries returned
6. Report: root cause = yfinance calendar type change; fix = hasattr guard; deployed SHA=xxx
```
