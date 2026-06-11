# GOVERNANCE AGENT — Standalone Implementation Prompt

Copy this entire message into Claude Code and execute.

---

## OBJECTIVE

Add a dedicated **Governance Analyst** agent to the Nivesh LangGraph multi-agent pipeline that systematically scans for Indian-market corporate governance red flags before any bullish thesis is built.

---

## WHY THIS FIRST

Your own feature analysis doc says it: *"Management quality is the ultimate arbiter of long-term capital allocation"* in Indian markets. No Indian retail stock app — not Zerodha Kite, not Groww, not Tickertape — has AI that proactively flags auditor resignations, promoter pledge spikes, SEBI surveillance additions, or CFO departures *before* the stock price reacts. This is your #1 differentiator.

This agent plugs into the existing graph with zero breaking changes. It's ~200 lines of Python and 5 files touched. Build it first — it feeds the Bull/Bear debate, the Reformatter, the iOS AnalysisScreen, and the StockProfileView Governance tab (later).

---

## THE FULL AI ANALYSIS CHAIN (CONTEXT)

```
iOS POST /analyze
  → Cache gating (analysis.py)
  → Deep Scan pre-processing (PKScreener + FinBERT)
  → Subprocess isolation (subprocess_runner.py)
  → TradingAgentsGraph.propagate():
      1. Factor Engine (deterministic RSI/MACD/SMA/Bollinger)
      2. Epistemic Feedback (prior analysis audit)
      3. 4-Analyst Committee (sequential, DeepSeek V4 Flash):
           Market → Sentiment → News → Fundamentals
      4. Bull/Bear Adversarial Debate (1 round)
      5. Research Manager → Trader → Risk Committee (3 profiles)
      6. Portfolio Manager (final verdict, structured output)
  → Claude Reformatter (structured JSON, dual cache breakpoints)
  → DeepSeek Reformatter fallback
  → Post-processing (Piotroski, live price, advisor matrix)
  → Save to DB → Return StockAnalysis JSON to iOS
  → iOS AnalysisScreen renders 11-section UI
```

The Governance Agent inserts as the **FIRST analyst** in Stage 4 — it runs before Market, Sentiment, News, and Fundamentals. Its report (`governance_report`) becomes input to every downstream agent.

---

## IMPLEMENTATION — 5 FILES, ~200 LINES

### FILE 1: Create the Governance Agent
**Path:** `backend/tradingagents-core/tradingagents/agents/analysts/governance_analyst.py`
**Action:** Create new file

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_insider_transactions,
    get_language_instruction,
)
from tradingagents.dataflows.config import get_config


def create_governance_analyst(llm):
    def governance_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)

        tools = [
            get_insider_transactions,
        ]

        system_message = (
            "You are an Indian corporate governance forensics analyst. Your sole purpose is to detect "
            "governance red flags BEFORE any bullish thesis is considered. You feed a downstream "
            "reformatter producing investment intelligence for a 10-year Dalal Street veteran investor.\n\n"
            "TOOLS: get_insider_transactions for SAST disclosures, insider trades, bulk/block deals, "
            "and promoter activity.\n\n"
            "MANDATORY SCAN — you MUST explicitly search for, flag, and quantify these event types:\n\n"
            "TIER 1 — EXISTENTIAL (flag with ⚠ CRITICAL):\n"
            "1. Statutory Auditor Resignation — query: 'resignation of statutory auditor' or "
            "'auditor resignation'. If found: state date, auditor name, reason disclosed, "
            "and the % price drop in the 5 days following the announcement.\n"
            "2. CFO / Managing Director / CEO Resignation — query: 'resignation of "
            "Managing Director' or 'resignation of Chief Executive Officer' or "
            "'resignation of Chief Financial Officer'. Flag even if 'personal reasons' cited.\n"
            "3. SEBI Regulatory Action — query for SEBI orders, SAT appeals, "
            "investigation notices, or surveillance measures (ASM/GSM list additions).\n"
            "4. Promoter Pledging Spike — if promoter_pledged_pct ≥ 30%, explain the "
            "margin-call cascade mechanism. If pledged % increased by >5% from prior "
            "quarter, flag as ⚠ CRITICAL regardless of absolute level.\n\n"
            "TIER 2 — HIGH SEVERITY (flag with ⚠ WARNING):\n"
            "5. Unsolicited SMS / SEBI Watchlist — check if stock appears on exchange "
            "surveillance lists (ASM long-term, ASM short-term, GSM). These stocks "
            "face trading restrictions and blocked settlement.\n"
            "6. Bulk/Block Deals — large promoter disposals >1% of equity in single "
            "transaction. Promoter selling into retail strength = distribution.\n"
            "7. Insider Cluster Selling — 3+ insiders selling within same quarter.\n"
            "8. Related Party Transaction Spike — significant increase in RPT volume "
            "or value relative to revenue.\n\n"
            "TIER 3 — MONITOR (flag with ⚠ NOTABLE):\n"
            "9. Pledge Invocation — any instance where lender invoked pledged shares.\n"
            "10. Credit Rating Downgrade — any rating agency action in last 6 months.\n"
            "11. Income Tax / GST Demand — material tax demands >2% of market cap.\n"
            "12. Delayed Filing — quarterly/annual report filing delayed beyond SEBI deadline.\n\n"
            "OUTPUT FORMAT — structured markdown with exact sections:\n"
            "1. GOVERNANCE SCORE: Single integer 0-100 (0 = worst governance, "
            "100 = pristine). Derive from: no flags=90-100, Tier 3 only=70-89, "
            "Tier 2=40-69, Tier 1=0-39, multiple Tier 1=0-19.\n"
            "2. RED FLAGS FOUND: Bulleted list. Each flag has: event type, date, "
            "quantified impact (bps/crore/% of market cap), and source (filing/SEBI/exchange).\n"
            "3. PROMOTER PLEDGE ANALYSIS: Current pledged %, trend vs prior quarter, "
            "margin-call risk assessment for this float size.\n"
            "4. INSIDER TRANSACTION SUMMARY: Last 6 months. Net insider buying/selling "
            "in crores. Cluster detection (3+ insiders same direction = signal).\n"
            "5. REGULATORY STANDING: ASM/GSM status, pending SEBI/SAT matters, "
            "exchange-imposed trading restrictions.\n"
            "6. GOVERNANCE VERDICT: One sentence. 'PASS' (score ≥70), 'CAUTION' "
            "(score 40-69), or 'FAIL' (score <40). This verdict overrides bullish "
            "fundamentals — a FAIL stock cannot receive a BUY recommendation.\n\n"
            "MANDATORY RULES:\n"
            "- NAME & NUMBER CONSTRAINT: Every qualitative claim must pair with "
            "a quantitative metric and specific operational driver. Never write "
            "'high pledging' — write 'promoter_pledged_pct at 78.3%, up 520bps "
            "QoQ, margin-call trigger at ₹XYZ based on 2.0x cover requirement.'\n"
            "- If yfinance returns None/NaN for any field, write 'Data not available "
            "for this period' — NEVER fabricate.\n"
            "- If no red flags found, state 'No material governance concerns detected "
            "for this period.' — DO NOT invent flags.\n"
            "- Append a Markdown table summarizing all checks at the end.\n"
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""
        if len(result.tool_calls) == 0:
            report = result.content

        # Auto-close unbalanced markdown markers before reformatter
        import re as _md_re
        if report:
            bold_count = len(_md_re.findall(r'\*\*', report))
            if bold_count % 2 != 0:
                report += "**"

        return {
            "messages": [result],
            "governance_report": report,
        }

    return governance_analyst_node
```

---

### FILE 2: Register the Agent
**Path:** `backend/tradingagents-core/tradingagents/agents/__init__.py`
**Action:** Add two lines

Find the imports section and add this line after the last analyst import:
```python
from .analysts.governance_analyst import create_governance_analyst
```

Find `__all__` list and add this inside the list (alphabetical order, after `create_fundamentals_analyst`):
```python
    "create_governance_analyst",
```

---

### FILE 3: Add Agent Spec to Execution Plan
**Path:** `backend/tradingagents-core/tradingagents/graph/analyst_execution.py`
**Action:** Add one entry to `ANALYST_NODE_SPECS` dict

Inside the `ANALYST_NODE_SPECS` dict, add BEFORE the `"market"` entry:

```python
    "governance": AnalystNodeSpec(
        key="governance",
        agent_node="Governance Analyst",
        clear_node="Msg Clear Governance",
        tool_node="tools_governance",
        report_key="governance_report",
    ),
```

---

### FILE 4: Add to Graph Setup
**Path:** `backend/tradingagents-core/tradingagents/graph/setup.py`
**Action:** Add 1 line to `analyst_factories` dict

Inside the `analyst_factories` dict in `setup_graph()`, add as first entry:

```python
            "governance": lambda: create_governance_analyst(self.quick_thinking_llm),
```

---

### FILE 5: Add Conditional Logic
**Path:** `backend/tradingagents-core/tradingagents/graph/conditional_logic.py`
**Action:** Add one method to `ConditionalLogic` class

Add this method after `should_continue_market`:

```python
    def should_continue_governance(self, state: AgentState):
        """Determine if governance analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_governance"
        return "Msg Clear Governance"
```

---

### FILE 6: Add Tool Node
**Path:** `backend/tradingagents-core/tradingagents/graph/trading_graph.py`
**Action:** Add 1 entry to `_create_tool_nodes()` dict

Inside the `_create_tool_nodes()` method's return dict, add as first entry:

```python
            "governance": ToolNode(
                [
                    get_insider_transactions,
                ]
            ),
```

Also update the `__init__` default parameter on line ~64 from:
```python
        selected_analysts=["market", "social", "news", "fundamentals"],
```
to:
```python
        selected_analysts=["governance", "market", "social", "news", "fundamentals"],
```

---

### FILE 7: Add governance_report to Initial State
**Path:** `backend/tradingagents-core/tradingagents/graph/propagation.py`
**Action:** Add 1 line to `create_initial_state()` return dict

Add this line after `"news_report": "",`:
```python
            "governance_report": "",
```

---

### FILE 8: Add governance_report to Subprocess Runner Output
**Path:** `backend/tradingagents-core/tradingagents/nivesh/subprocess_runner.py`
**Action:** Add 1 line to `_worker()` queue.put dict

Add this line after `"news_report"` entry:
```python
                "governance_report": final_state.get("governance_report", ""),
```

---

### FILE 9: Add governance_report to State Logger
**Path:** `backend/tradingagents-core/tradingagents/graph/trading_graph.py`
**Action:** Add 1 line to `_log_state()` dict

Add this line after `"news_report"` entry in the dictionary:
```python
            "governance_report": final_state["governance_report"],
```

---

### FILE 10: Inject Governance into Reformatter Prompt
**Path:** `backend/services/orchestrator.py`
**Action:** Find where `raw_output` is constructed (around line 100-150 in the `analyze()` function) and add governance_report context.

Find the block that constructs the raw_output string (search for `"Market report:"` in the file). Add this BEFORE the market report line:

```python
    governance_report = result.get("governance_report", "")
    if governance_report:
        raw_output = f"GOVERNANCE FORENSICS REPORT:\n{governance_report}\n\n---\n\n{raw_output}"
```

---

### FILE 11: Add governance fields to System Prompt
**Path:** `backend/prompts.py`
**Action:** In `INDIAN_MARKET_SYSTEM_PROMPT`, inside the `key_factors` section of the JSON schema, add this after `"management_quality"`:

```json
    "governance_score": <integer 0-100>,
    "governance_red_flags": ["<flag 1>", "<flag 2>"],
```

And in the `fundamentals_snapshot` section, ensure these fields are populated from governance data:
```
    "promoter_pledged_pct": <number or null>,
    "promoter_pledged_trend": <string or null>,
```

Also add this instruction to the ANALYSIS PRIORITIES section (after item 1):
```
1a. Governance Red Flags — if governance_score < 40, cap confidence_pct at 40 regardless of other factors. A FAIL governance verdict overrides all bullish signals.
```

---

## VERIFICATION

After implementing, verify by:

1. **Unit check:** Run `python -c "from tradingagents.agents.analysts.governance_analyst import create_governance_analyst; print('OK')"`
2. **Graph check:** Run `python -c "from tradingagents.graph.trading_graph import TradingAgentsGraph; g = TradingAgentsGraph(); print('Graph compiled OK with governance agent')"`
3. **End-to-end test:** POST to `/analyze` with `{"ticker": "RELIANCE", "exchange": "NSE", "deep_scan": true}` and verify `governance_score` and `governance_red_flags` appear in the response JSON.
4. **iOS check:** Verify the `StockAnalysis` Codable model parses the new fields without crashing (they're optional arrays/ints so existing code handles nil gracefully).

---

## CRITICAL "DO NOT" RULES

- Do NOT change the graph edge wiring in `setup.py` — the new agent uses the existing sequential path (it auto-wires as first analyst because `"governance"` is now first in `selected_analysts`).
- Do NOT remove the existing News Analyst's governance checks — the dedicated agent is additive.
- Do NOT change the `AgentState` TypedDict in `agent_states.py` — `governance_report` is a free key, LangGraph state is a plain dict.
- Do NOT change the iOS models yet — the new fields are additive and nil-safe.
- Do NOT touch the reformatter model constants or temperature settings.

---

## EXPECTED RESULT

After this change, every `/analyze` request will:
- Run Governance Analyst FIRST (before any price/momentum analysis)
- Inject its `governance_report` into the Bull Researcher, Bear Researcher, Research Manager, Trader, Risk Committee, and Portfolio Manager prompts
- Surface `governance_score` (0-100) and `governance_red_flags` (array of strings) in the final JSON returned to iOS
- Cause stocks with governance FAIL verdicts to automatically cap confidence at 40% and never receive BUY/OVERWEIGHT

This is the highest-leverage 2-hour investment you can make in the Nivesh AI pipeline.
