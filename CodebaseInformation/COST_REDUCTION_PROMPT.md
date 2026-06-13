# AI ANALYSIS COST REDUCTION — Preserve Quality, Cut Cost

Paste into Claude Code. Execute without asking questions.
Follow Karpathy guideline: implement end-to-end, ship working changes, verify each.

---

## WHERE THE MONEY GOES

Per analysis, ~17 LLM calls:

| Tier | Model | Calls | Cost per call | % of total cost |
|------|-------|-------|--------------|:---:|
| Tier 1 | DeepSeek V4 Flash | ~14 | $0.14/1M in, $0.28/1M out | ~25% |
| Tier 2 | Claude Haiku 4.5 | 2 | $0.80/1M in, $4.00/1M out | ~15% |
| Tier 3 | Claude Sonnet | 1 (reformatter) | $3.00/1M in, $15.00/1M out, 4000-8000 max_tokens | **~60%** |

The reformatter alone is 60% of cost. Kill it first.

---

## FIX 1: Kill Claude Sonnet Reformatter (biggest win, zero quality loss)

**File:** `backend/services/orchestrator.py`

The Portfolio Manager already uses Pydantic structured output (`PortfolioDecision` schema). If the PM produces valid structured JSON, we don't need a separate reformatting pass.

**Change:** Instead of `reformat_with_claude()` (Claude Sonnet, Tier 3), use `reformat_with_deepseek()` (DeepSeek V4 Flash, Tier 1) as the primary reformatter. Sonnet becomes the fallback only when DeepSeek output is unparseable.

```python
# Find the reformat_with_claude function (~line 459)
# Add a new function BEFORE it:

def reformat_with_deepseek(raw_output: str, full_ticker: str, exchange: str,
                           prior_analyses: list | None = None) -> dict:
    """Primary reformatter: DeepSeek V4 Flash (Tier 1, cheapest).
    Only falls back to Claude Sonnet on parse failure."""
    
    # Try DeepSeek first (cheap)
    for attempt in range(2):
        try:
            ds_raw = _deepseek_chat(
                messages=[
                    {"role": "system", "content": INDIAN_MARKET_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Reformat the following analysis for {full_ticker} ({exchange}) into valid JSON.\n\n{raw_output[:8000]}"},
                ],
                max_tokens=2000,  # was 4000-8000, cut in half
                temperature=0,
                log_endpoint="reformat_deepseek",
            )
            result = _extract_json(ds_raw)
            if result and result.get("signal"):
                result = _normalize_response(result)
                return result
        except Exception:
            continue
    
    # DeepSeek failed — fall back to Claude Sonnet (expensive, but reliable)
    return reformat_with_claude(raw_output, full_ticker, exchange, prior_analyses)
```

Then in the `analyze()` function (~line 1242), replace:
```python
result = reformat_with_claude(raw_output, full_ticker, exchange, prior_analyses=prior)
```
with:
```python
result = reformat_with_deepseek(raw_output, full_ticker, exchange, prior_analyses=prior)
```

**Expected savings:** 50-60% per analysis. DeepSeek reformat costs ~$0.002 vs Claude Sonnet at ~$0.03-0.06 per call.

---

## FIX 2: Skip Full Pipeline When Governance FAILS

**File:** `backend/tradingagents-core/tradingagents/graph/trading_graph.py`

If governance_score < 20, the stock has CRITICAL red flags (auditor resigned, SEBI action, promoter pledging >50%). No amount of bullish debate can override this. Skip 12 LLM calls.

In `propagate()`, after the governance agent runs (~line 430 area):

```python
# After governance agent completes, check if we can fast-track
governance_report = final_state.get("governance_report", "")
if "GOVERNANCE FAIL" in governance_report or "CRITICAL" in governance_report:
    # Count critical flags
    critical_count = governance_report.count("⚠ CRITICAL")
    if critical_count >= 2:
        logger.info(f"[cost-save] {company_name}: {critical_count} critical governance flags. Fast-tracking to Portfolio Manager.")
        
        # Skip all remaining agents. Build a minimal state that flows to PM.
        final_state["market_report"] = "Skipped — governance FAIL overrides"
        final_state["sentiment_report"] = "Skipped — governance FAIL overrides"
        final_state["news_report"] = "Skipped — governance FAIL overrides"
        final_state["fundamentals_report"] = "Skipped — governance FAIL overrides"
        final_state["investment_debate_state"]["history"] = "Debate skipped — governance FAIL"
        final_state["investment_debate_state"]["judge_decision"] = "SELL — governance FAIL"
        final_state["trader_investment_plan"] = "SELL — governance FAIL"
        final_state["risk_debate_state"]["history"] = "Risk review skipped — governance FAIL"
        
        # Jump directly to Portfolio Manager for final verdict
        # (the graph will route there since all intermediate nodes are "done")
```

Also inject into the PM prompt context: "ALL ANALYST REPORTS WERE SKIPPED because the governance agent found 2+ CRITICAL red flags. The only acceptable verdict is SELL or AVOID. Confidence must be capped at 30."

**Expected savings:** 12 DeepSeek calls skipped (~70% of Tier 1 cost) for governance-fail stocks. These are exactly the stocks where the analysis adds zero value — the verdict is predetermined.

---

## FIX 3: Standard Scans: 1 Debate Round, Not 3

**File:** `backend/tradingagents-core/tradingagents/default_config.py`

The debate currently runs 3 rounds (we changed this earlier). Deep scan should keep 3. Standard scan should use 1.

**Change:** The orchestrator already distinguishes `deep_scan=True` vs standard. Pass this to the config:

In `backend/services/orchestrator.py`, where `run_trading_agents()` is called (~line 410):

```python
# Before building config:
debate_rounds = 3 if deep_scan else 1
risk_rounds = 2 if deep_scan else 1

config["max_debate_rounds"] = debate_rounds
config["max_risk_discuss_rounds"] = risk_rounds
```

**Expected savings:** 4 DeepSeek calls per standard analysis (Bull x2 + Bear x2 skipped). Standard scans are the majority of user analyses. Deep scans keep full quality.

---

## FIX 4: Drop Sentiment Analyst for Indian Stocks (Standard Scans)

**File:** `backend/tradingagents-core/tradingagents/nivesh/subprocess_runner.py`

The sentiment analyst scrapes StockTwits and Reddit. For Indian stocks, these sources are sparse — it frequently returns "insufficient data" or noise. Skip it for standard scans.

In `_worker()`, where `selected_analysts` is built (~line 90):

```python
# For standard scans, skip sentiment (sparse for Indian equities)
if config_overrides.get("deep_scan"):
    selected_analysts = ["governance", "market", "social", "news", "fundamentals"]
else:
    selected_analysts = ["governance", "market", "news", "fundamentals"]  # no social
```

**Expected savings:** 1 DeepSeek call per standard analysis.

---

## FIX 5: Reduce max_tokens Across All Agents

**File:** `backend/services/orchestrator.py`

Current: `max_tokens = 8000` for extreme, `4000` for standard. DeepSeek multiplies this by 5 internally (line 57 of llm_utils: `effective_max = max(max_tokens * 5, 512)`). So standard scans allow 4000 * 5 = 20,000 output tokens per agent. That's enormous for a report that gets summarized anyway.

**Change (~line 410-422):**

```python
if is_extreme:
    config["max_tokens"] = 4000   # was 8000 — still plenty for deep analysis
else:
    config["max_tokens"] = 1000   # was 4000 — 1000*5=5000 effective, enough for a concise report
```

Also reduce the reformatter max_tokens (~line 489):
```python
reformat_max_tokens = 2000 if is_extreme else 1000  # was 8000/4000
```

**Expected savings:** 50-75% reduction in output tokens. Output tokens cost more than input tokens (2x for DeepSeek, 5x for Claude). This directly cuts the most expensive part of each call.

---

## FIX 6: Cache Repeated Analyses (Semantic Dedup)

**File:** `backend/routers/analysis.py`

If a user re-analyzes the same stock within 30 minutes with the same parameters, return the cached analysis. Don't re-run the pipeline.

In the `analyze()` endpoint, before spawning the subprocess:

```python
# Check for recent identical analysis (same ticker, same deep_scan flag, <30 min old)
from database import AnalysisHistory, get_session
with get_session() as sess:
    recent = sess.query(AnalysisHistory).filter(
        AnalysisHistory.ticker == ticker.upper(),
        AnalysisHistory.created_at >= datetime.utcnow() - timedelta(minutes=30),
    ).order_by(AnalysisHistory.created_at.desc()).first()
    
    if recent:
        # Check if deep_scan matches (store deep_scan_used in full_json)
        try:
            fj = json.loads(recent.full_json) if isinstance(recent.full_json, str) else recent.full_json
            if fj.get("deep_scan_used") == deep_scan:
                return recent  # serve cached — zero LLM cost
        except Exception:
            pass
```

**Expected savings:** 100% for repeat analyses. Common pattern: user analyzes, reads report, tweaks parameters, re-analyzes.

---

## NET IMPACT

| Fix | What changes | Cost reduction |
|-----|-------------|:---:|
| 1. DeepSeek reformatter | Kill Claude Sonnet, use DeepSeek | **50-60%** |
| 2. Skip on governance FAIL | Fast-track to PM on 2+ critical flags | **70% on ~5% of stocks** |
| 3. Standard = 1 debate round | deep_scan→3 rounds, standard→1 | **~25% on standard scans** |
| 4. Drop sentiment (standard) | Skip social media analyst for Indian stocks | **~7% on standard scans** |
| 5. Reduce max_tokens | Cap output at 1000 base (5000 effective) | **30-50% on output tokens** |
| 6. Cache repeated analyses | 30-min dedup on same ticker+params | **100% on repeats** |

**Combined:** A standard analysis drops from ~17 LLM calls to ~9 calls, with the most expensive call (Sonnet) eliminated entirely. Estimated per-analysis cost: $0.01-0.02 vs $0.05-0.10 before. Deep scan quality unchanged.

---

## VERIFICATION

```bash
# Check token costs before/after on the server
ssh root@165.22.221.18 "journalctl -u nivesh.service -n 200 | grep -E 'token|cost|DeepSeek|Sonnet|Haiku' | tail -20"

# Run a standard analysis and check it still produces valid JSON
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"ticker":"TCS","exchange":"NSE","deep_scan":false}' \
  --max-time 180 | python3 -m json.tool | grep -E "signal|confidence|governance_score"
```

## DO NOT
- Don't remove the Claude Sonnet fallback — keep it for when DeepSeek reformat fails
- Don't skip agents for deep_scan=True — only standard scans get reduced
- Don't change agent prompts or the INDIAN_MARKET_SYSTEM_PROMPT
- Don't reduce quality for deep scans — those are power users who expect full analysis
- Don't hardcode model names — use existing constants from llm_utils
