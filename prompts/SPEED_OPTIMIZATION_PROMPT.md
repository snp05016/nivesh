# Speed Optimization Implementation Prompt

## Objective
Reduce AI analysis latency from ~12 min (normal) / ~20 min (extreme) to ~6 min / ~8 min without any quality degradation.

## Mandatory Fixes (Zero Quality Impact)

### Fix 1: Parallelize Calibration Pipeline
**File**: `backend/services/orchestrator.py`  
**Function**: `_run_calibration_pipeline()` (or equivalent)  
**Change**: Wrap all 8 calibration calls in `ThreadPoolExecutor(max_workers=4)`  
**Current**: Sequential await per calibration step (~40s)  
**Target**: Parallel execution (~5-10s)  
**Risk**: None — identical math, same results

### Fix 2: Pre-start Technical Indicators Computation
**File**: `backend/services/orchestrator.py` → `analyze()`  
**Change**: Launch `compute_indicators()` in background thread **before** LangGraph starts  
```python
from concurrent.futures import ThreadPoolExecutor
_indicator_future = executor.submit(compute_indicators, ns_ticker)
# ... run LangGraph ...
indicators = _indicator_future.result(timeout=120)
```
**Current**: Indicators computed after LangGraph completes (~50s)  
**Target**: Overlapped with LangGraph execution  
**Risk**: None — pure timing optimization

### Fix 5: Compress Reformatter Input
**File**: `backend/services/orchestrator.py` → `reformat_with_claude()` / `reformat_with_deepseek()`  
**Change**: Feed only PM conclusion + calibration block to reformatter (not full 8000-char raw dump)  
```python
# Extract only what reformatter needs
pm_conclusion = extract_pm_conclusion(raw_output)
calibration_block = extract_calibration_block(raw_output)
user_message = f"PM Conclusion:\n{pm_conclusion}\n\nCalibration:\n{calibration_block}"
```
**Current**: `raw_output[:8000]` (full debate transcript)  
**Target**: ~4500 chars (PM decision + numbers only)  
**Risk**: None — reformatter only structures JSON, doesn't "learn" from debate verbosity

### Fix 6: Pre-fetch Live yfinance Data
**File**: `backend/services/orchestrator.py` → `analyze()`  
**Change**: Start 1yr history fetch in background alongside LangGraph  
```python
_hist_future = executor.submit(lambda: yf.Ticker(ns_ticker).history(period="1y"))
# ... run LangGraph ...
hist = _hist_future.result(timeout=60)
```
**Current**: Fetched in `_inject_live_data()` after reformatting (~25s)  
**Target**: Overlapped with LangGraph  
**Risk**: None — same data, earlier fetch

### Fix 8: Enable Analyst Concurrency (2 parallel)
**File**: `backend/services/orchestrator.py` → `build_ta_config()` / `OptimizedGraphSetup`  
**Change**: 
```python
# In build_ta_config():
config["analyst_concurrency_limit"] = 2  # was 1

# In OptimizedGraphSetup.__init__():
self.analyst_concurrency_limit = config.get("analyst_concurrency_limit", 2)
```
**Current**: 4 analysts run sequentially (~6 min)  
**Target**: 2-at-a-time parallel (~3 min)  
**Risk**: Near-zero — analysts have independent tool access. Only risk: NSE/yfinance rate limits (mitigate with retry/backoff in tool wrappers)

---

## Negligible Quality Impact Fixes (~2-3% intermediate depth reduction, 0% final output)

### Fix 3: Cap Analyst Output Length (600 words max)
**Files**: 
- `backend/services/orchestrator.py` — `MARKET_ANALYST_PERSONA`, `FUNDAMENTALS_ANALYST_PERSONA`, `GOVERNANCE_ANALYST_PERSONA`, `NEWS_ANALYST_PERSONA`
- `backend/prompts.py` — same persona strings

**Change**: Append to each persona:
```
OUTPUT LENGTH LIMIT: Maximum 600 words. Be concise. Every sentence must carry a metric or catalyst. No fluff.
```

**Current**: "Write a very detailed and nuanced report" (800-1200 words typical)  
**Target**: 600 words max per analyst  
**Honest Impact**: Intermediate reports lose some nuance, but Bull/Bear researchers re-synthesize from scratch. Final PM decision unchanged.

### Fix 4: Cap Risk Analyst Debate Length
**Files**: `backend/services/orchestrator.py` — `create_aggressive_debator`, `create_neutral_debator`, `create_conservative_debator` personas (or wherever these are defined)

**Change**: Add to each risk analyst persona:
```
OUTPUT LENGTH LIMIT: Maximum 400 words. Focus on actionable risk scenarios with quantified impact.
```

**Current**: Unbounded verbose debate  
**Target**: Concise risk scenarios  
**Honest Impact**: Same — Portfolio Manager reads all three and decides. Debate verbosity doesn't improve final decision.

---

## Implementation Order (Do sequentially, verify each)

1. **Fix 8** — Change `analyst_concurrency_limit = 2` in config (5 min task, immediate 90s savings)
2. **Fix 1** — ThreadPoolExecutor for calibration (10 min task)
3. **Fix 2** — Background indicator computation (10 min task)
4. **Fix 6** — Background yfinance history fetch (5 min task)
5. **Fix 5** — Compress reformatter input (10 min task, requires extracting PM conclusion helper)
6. **Fix 3** — Add 600-word caps to 4 analyst personas (5 min task)
7. **Fix 4** — Add 400-word caps to 3 risk analyst personas (5 min task)

---

## Verification Checklist

After each fix:
- [ ] Run `pytest backend/tests/test_orchestrator.py -v` (or relevant test suite)
- [ ] Manual smoke test: `curl -X POST /api/analyze -d '{"ticker":"RELIANCE","scan_type":"standard"}'` — confirm < 8 min
- [ ] Verify JSON output structure unchanged (all required fields present)
- [ ] Check `governance_score`, `signal`, `confidence_pct` match pre-fix baseline for same ticker
- [ ] Monitor logs for rate-limit errors (Fix 8) — add exponential backoff if needed

---

## Files to Modify (Summary)

| File | Fixes |
|------|-------|
| `backend/services/orchestrator.py` | 1, 2, 5, 6, 8, 3, 4 |
| `backend/prompts.py` | 3 (persona strings) |
| `backend/services/llm_utils.py` | (verify model config unchanged) |

---

## Do NOT Implement

- Fix 7 (deepseek-chat for data analysts in extreme) — genuine quality trade-off on governance forensics
- Any changes to `INDIAN_MARKET_SYSTEM_PROMPT` core logic
- Any changes to `_normalize_response()` or output schema
- Any changes to Bull/Bear/Portfolio Manager prompts

---

## Expected Results

| Mode | Before | After | Savings |
|------|--------|-------|---------|
| Normal | ~12 min | ~6 min | ~6 min (50%) |
| Extreme | ~20 min | ~8-9 min | ~11 min (55%) |

Quality: Identical final JSON output. Only intermediate analyst verbosity reduced.