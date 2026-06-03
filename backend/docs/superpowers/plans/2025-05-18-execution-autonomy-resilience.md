# Task 3: Execution Autonomy & Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement robust error handling, retries, and session management for the Indian Stock App to ensure high reliability and consistent model usage.

**Architecture:** 
- Enhance `database.py` with a context-managed session helper that handles rollbacks and closure.
- Implement exponential backoff retry logic for all external API calls (yfinance and Anthropic).
- Consolidate model identifiers to a single constant `HAIKU_MODEL`.
- Strengthen JSON parsing and validation for AI outputs.

**Tech Stack:** Python, SQLAlchemy, Anthropic SDK, yfinance

---

### Task 1: Robust Database Session Management

**Files:**
- Modify: `database.py:187-189`

- [ ] **Step 1: Update `get_session` to be a context manager**

```python
from contextlib import contextmanager

@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        # We don't auto-commit here because some operations might be read-only
        # and some might call session.commit() internally.
        # But we DO handle rollbacks.
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

- [ ] **Step 2: Verify imports in `database.py`**
Ensure `from contextlib import contextmanager` is added.

### Task 2: Consolidate Model Identifiers

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Replace hardcoded Haiku model strings with `HAIKU_MODEL`**

Update `build_ta_config()`:
```python
    config["deep_think_llm"] = HAIKU_MODEL
    config["quick_think_llm"] = HAIKU_MODEL
```

Update Smart Cache (approx line 662):
```python
                        resp = client.messages.create(
                            model=HAIKU_MODEL,
                            max_tokens=10,
                            messages=[{"role": "user", "content": prompt}]
                        )
```

Update `/morning-summary` (approx line 1275):
```python
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
```

### Task 3: Robust Retries for External Calls

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Enhance `_yf_fetch_info` with exponential backoff**

```python
def _yf_fetch_info(sym: str) -> dict:
    """Fetch yfinance info with 3 attempts and exponential backoff."""
    import time
    import random
    for attempt in range(3):
        try:
            info = yf.Ticker(sym).info
            if info and (info.get("currentPrice") or info.get("regularMarketPrice")):
                return info
        except Exception as e:
            print(f"[YF] Attempt {attempt+1} failed for {sym}: {e}")
            if attempt < 2:
                # Exponential backoff: 1.5s, 3s, etc. + jitter
                sleep_time = (1.5 * (2 ** attempt)) + (random.random() * 0.5)
                time.sleep(sleep_time)
    return {}
```

- [ ] **Step 2: Add retry logic to `reformat_with_claude`**

```python
    import time
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=SONNET_MODEL,
                max_tokens=2000,
                system=system_array,
                messages=[{"role": "user", "content": user_message}],
                temperature=0 # Strict deterministic output
            )
            break
        except Exception as e:
            print(f"[Anthropic] Reformat attempt {attempt+1} failed: {e}")
            if attempt == 2: raise
            time.sleep(1.0 * (2 ** attempt))
```

- [ ] **Step 3: Add retry logic and `HAIKU_MODEL` to Smart Cache Anthropic call**

```python
                        import time
                        for attempt in range(3):
                            try:
                                resp = client.messages.create(
                                    model=HAIKU_MODEL,
                                    max_tokens=10,
                                    messages=[{"role": "user", "content": prompt}]
                                )
                                break
                            except Exception as e:
                                print(f"[Anthropic] Smart cache attempt {attempt+1} failed: {e}")
                                if attempt == 2: raise
                                time.sleep(1.0 * (2 ** attempt))
```

- [ ] **Step 4: Add retry logic and `HAIKU_MODEL` to `/morning-summary` Anthropic call**

```python
        import time
        for attempt in range(3):
            try:
                response = client.messages.create(
                    model=HAIKU_MODEL,
                    max_tokens=400,
                    messages=[{"role": "user", "content": prompt}],
                )
                break
            except Exception as e:
                print(f"[Anthropic] Morning summary attempt {attempt+1} failed: {e}")
                if attempt == 2: raise
                time.sleep(1.0 * (2 ** attempt))
```

### Task 4: Strict JSON Validation & Fallback

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Implement robust JSON extraction helper**

```python
def _extract_json_from_text(text: str) -> str:
    """Extract JSON from markdown code blocks or return raw text."""
    if "```json" in text:
        return text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        return text.split("```")[1].strip()
    return text.strip()
```

- [ ] **Step 2: Update `reformat_with_claude` to use the helper and handle parse errors**

```python
    raw_json = _extract_json_from_text(response.content[0].text)
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse reformatted JSON: {e}")
        # Return a minimal valid structure if parsing fails
        return {
            "signal": "HOLD",
            "confidence_pct": 0,
            "target_prices": {},
            "key_factors": {"indian_market_sentiment": "Parse error occurred."}
        }
```

- [ ] **Step 3: Update `/morning-summary` to use the helper and handle parse errors**

```python
        raw = _extract_json_from_text(response.content[0].text)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse morning summary JSON: {e}")
            parsed = fallback
```


### Task 5: Final Verification

- [ ] **Step 1: Run `verify_task1.py` and other existing tests**
- [ ] **Step 2: Manually verify a few tickers to ensure everything still works**
