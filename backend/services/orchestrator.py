"""
AI Orchestration Service — extracted from main.py to resolve the God-Node anti-pattern.

Contains the full 8-stage AI analysis pipeline:
- analyze() — main entry point for stock analysis
- reformat_with_claude() — Claude Sonnet → DeepSeek V4 Flash reformatter
- run_trading_agents() — LangGraph-based multi-agent propagation
- Supporting graph setup, normalization, and JSON extraction utilities.

All state is DB-backed or passed as arguments — no module-level shared mutable state.
"""

import os
import json
import copy
import math
import time
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Load environment
# ---------------------------------------------------------------------------
from dotenv import load_dotenv

_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

# ---------------------------------------------------------------------------
# Third-party
# ---------------------------------------------------------------------------
import yfinance as yf
import anthropic
from services.llm_utils import (
    get_deepseek_client,
    deepseek_chat,
    HAIKU_MODEL,
    SONNET_MODEL,
    DEEPSEEK_MODEL,
)
# backward-compat aliases for internal callers
_get_deepseek_client = get_deepseek_client
_deepseek_chat = deepseek_chat

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, START, END

# ---------------------------------------------------------------------------
# Application — helpers, DB, prompts, services
# ---------------------------------------------------------------------------
from helpers import (
    EXCHANGE_SUFFIX,
    _resolve_ticker,
    _to_ns,
    _yf_price,
    _yf_fetch_info,
    _log_token_usage,
    TOKEN_LOG_PATH,
)

from database import (
    get_session,
    save_analysis,
    get_analysis_for_date,
    get_all_ticker_history,
    AdvisorInsight,
    AnalysisHistory,
    NewsArticle,
    PKScreenerSignal,
)

from prompts import INDIAN_MARKET_SYSTEM_PROMPT, NEWS_ANALYST_PERSONA

from services.staleness import compute_staleness
from services.piotroski import compute_piotroski

# ---------------------------------------------------------------------------
# TradingAgents framework
# ---------------------------------------------------------------------------
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.agents import (
    create_bull_researcher,
    create_bear_researcher,
    create_research_manager,
    create_trader,
    create_aggressive_debator,
    create_neutral_debator,
    create_conservative_debator,
    create_portfolio_manager,
    create_msg_delete,
)
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.agents.utils.agent_utils import get_instrument_context_from_state
from tradingagents.graph.analyst_execution import build_analyst_execution_plan
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.setup import GraphSetup

# ═════════════════════════════════════════════════════════════════════════════
# Model Identifiers
# ═════════════════════════════════════════════════════════════════════════════
# LLM client and model constants — now in services.llm_utils (single source)
# ═════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════
# Constants: Prompt Caching Blocks
# ═════════════════════════════════════════════════════════════════════════════

BASE_INSTITUTIONAL_INSTRUCTION = (
    "You are a helpful AI assistant, collaborating with other assistants. "
    "Use the provided tools to progress towards answering the question. "
    "If you are unable to fully answer, that's OK; another assistant with "
    "different tools will help where you left off. Execute what you can to "
    "make progress. If you or any other assistant has the FINAL TRANSACTION "
    "PROPOSAL: **BUY/HOLD/SELL** or deliverable, prefix your response with "
    "FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
)

MARKET_ANALYST_PERSONA = (
    "You are a trading assistant tasked with analyzing financial markets. "
    "Your role is to select the **most relevant indicators** for a given market "
    "condition or trading strategy from the following list. The goal is to choose "
    "up to **8 indicators** that provide complementary insights without redundancy.\n\n"
    "Indicators:\n"
    "- close_50_sma, close_200_sma, close_10_ema (Moving Averages)\n"
    "- macd, macds, macdh (Momentum)\n"
    "- rsi (Momentum)\n"
    "- boll, boll_ub, boll_lb (Volatility)\n"
    "- atr (Volatility)\n"
    "- vwma (Volume)\n\n"
    "Tool Definitions:\n"
    "- get_stock_data(symbol, start_date, end_date): Retrieve OHLCV price data.\n"
    "- get_indicators(symbol, indicator, curr_date, look_back_days): Get specific technical indicators.\n"
    "- get_verified_market_snapshot(symbol, date): Source of truth for exact price/indicator values.\n\n"
    "Write a very detailed and nuanced report. Append a Markdown table for key points."
)

    FUNDAMENTALS_ANALYST_PERSONA = (
        "You are a researcher tasked with analyzing fundamental information. "
        "Write a comprehensive report on the company's financials (balance sheet, "
        "cash flow, income statement) and profile to gain a full view for traders.\n\n"
        "Tool Definitions:\n"
        "- get_fundamentals(ticker, curr_date): Comprehensive fundamental summary.\n"
        "- get_balance_sheet(ticker, freq, curr_date): Balance sheet details.\n"
        "- get_cashflow(ticker, freq, curr_date): Cash flow details.\n"
        "- get_income_statement(ticker, freq, curr_date): Income statement details.\n\n"
        "Provide specific, actionable insights. Append a Markdown table for key points."
    )

    GOVERNANCE_ANALYST_PERSONA = (
        "You are an Indian corporate governance forensics analyst. "
        "Scan for governance red flags: auditor resignations, CFO/MD departures, "
        "SEBI actions, promoter pledging spikes, bulk/block deals, insider cluster "
        "selling, ASM/GSM listings, credit downgrades, and regulatory penalties. "
        "Output a governance score (0-100) and a structured red flags report.\n\n"
        "Tool Definitions:\n"
        "- get_news(query, start_date, end_date): Search governance events.\n"
        "- get_insider_transactions(curr_date, look_back_days, ticker): SAST+insider trades.\n\n"
        "NAME & NUMBER: Every claim must have a figure, date, or rupee amount. "
        "Never fabricate. Append a Markdown table summary."
    )

# ═════════════════════════════════════════════════════════════════════════════
# JSON Extraction Helper
# ═════════════════════════════════════════════════════════════════════════════


def _extract_json_from_text(text: str) -> str:
    """Extract primary JSON envelope from LLM output.
    Uses regex to isolate the outermost JSON object, ignoring any JSON
    blocks embedded inside markdown explanations or conversational text.
    """
    import re as _re
    text = text.strip()
    # Priority 1: ```json ... ``` fenced block (lazy match for outermost)
    m = _re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, _re.DOTALL)
    if m:
        return m.group(1).strip()
    # Priority 2: outermost { ... } via regex
    m = _re.search(r"\{.*\}", text, _re.DOTALL)
    if m:
        return m.group(0).strip()
    # Priority 3: legacy split-based fallback
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            return parts[1].strip()
    return text


# ═════════════════════════════════════════════════════════════════════════════
# Optimized Analyst Node Factory
# ═════════════════════════════════════════════════════════════════════════════


def create_optimized_analyst_node(llm, persona: str, report_key: str, tools: list):
    def analyst_node(state):
        instrument_context = get_instrument_context_from_state(state)
        current_date = state["trade_date"]

        # Dual-Breakpoint Cache Strategy for Analyst Node
        # 1. Static Institutional Instruction (Shared across all nodes)
        # 2. Specific Persona & Tools (Stable for this analyst type)
        # 3. Volatile Context (Ticker, Date - in HumanMessage)

        system_blocks = [
            {
                "type": "text",
                "text": BASE_INSTITUTIONAL_INSTRUCTION,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": f"{persona}\n\nYou have access to the following tools: {', '.join([t.name for t in tools])}.",
                "cache_control": {"type": "ephemeral"},
            },
        ]

        volatile_context = f"The current trading date is {current_date}. {instrument_context}"

        messages = [
            SystemMessage(content=system_blocks),
            MessagesPlaceholder(variable_name="messages"),
            HumanMessage(content=volatile_context),
        ]

        prompt = ChatPromptTemplate.from_messages(messages)
        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])
        report = result.content if not result.tool_calls else ""

        return {
            "messages": [result],
            f"{report_key}_report": report,
        }

    return analyst_node


# ═════════════════════════════════════════════════════════════════════════════
# Optimized Graph Setup
# ═════════════════════════════════════════════════════════════════════════════


class OptimizedGraphSetup(GraphSetup):
    def setup_graph(self, selected_analysts=["governance", "market", "news", "fundamentals"]):
        from tradingagents.agents.utils.agent_utils import (
            get_stock_data,
            get_indicators,
            get_news,
            get_global_news,
            get_insider_transactions,
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
        )

        plan = build_analyst_execution_plan(
            selected_analysts, concurrency_limit=self.analyst_concurrency_limit
        )

        analyst_factories = {
            "governance": lambda: create_optimized_analyst_node(
                self.quick_thinking_llm,
                GOVERNANCE_ANALYST_PERSONA,
                "governance",
                [get_news, get_insider_transactions],
            ),
            "market": lambda: create_optimized_analyst_node(
                self.quick_thinking_llm,
                MARKET_ANALYST_PERSONA,
                "market",
                [get_stock_data, get_indicators],
            ),
            "news": lambda: create_optimized_analyst_node(
                self.quick_thinking_llm,
                NEWS_ANALYST_PERSONA,
                "news",
                [get_news, get_global_news, get_insider_transactions],
            ),
            "fundamentals": lambda: create_optimized_analyst_node(
                self.quick_thinking_llm,
                FUNDAMENTALS_ANALYST_PERSONA,
                "fundamentals",
                [get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement],
            ),
            "social": lambda: create_optimized_analyst_node(
                self.quick_thinking_llm,
                "You are a sentiment analyst.",
                "sentiment",
                [get_news],
            ),
        }

        bull_researcher_node = create_bull_researcher(self.quick_thinking_llm)
        bear_researcher_node = create_bear_researcher(self.quick_thinking_llm)
        research_manager_node = create_research_manager(self.deep_thinking_llm)
        trader_node = create_trader(self.quick_thinking_llm)
        aggressive_analyst = create_aggressive_debator(self.quick_thinking_llm)
        neutral_analyst = create_neutral_debator(self.quick_thinking_llm)
        conservative_analyst = create_conservative_debator(self.quick_thinking_llm)
        portfolio_manager_node = create_portfolio_manager(self.deep_thinking_llm)

        workflow = StateGraph(AgentState)
        for spec in plan.specs:
            workflow.add_node(spec.agent_node, analyst_factories[spec.key]())
            workflow.add_node(spec.clear_node, create_msg_delete())
            workflow.add_node(spec.tool_node, self.tool_nodes[spec.key])

        workflow.add_node("Bull Researcher", bull_researcher_node)
        workflow.add_node("Bear Researcher", bear_researcher_node)
        workflow.add_node("Research Manager", research_manager_node)
        workflow.add_node("Trader", trader_node)
        workflow.add_node("Aggressive Analyst", aggressive_analyst)
        workflow.add_node("Neutral Analyst", neutral_analyst)
        workflow.add_node("Conservative Analyst", conservative_analyst)
        workflow.add_node("Portfolio Manager", portfolio_manager_node)

        workflow.add_edge(START, plan.specs[0].agent_node)
        for i, spec in enumerate(plan.specs):
            workflow.add_conditional_edges(
                spec.agent_node,
                getattr(self.conditional_logic, f"should_continue_{spec.key}"),
                [spec.tool_node, spec.clear_node],
            )
            workflow.add_edge(spec.tool_node, spec.agent_node)
            if i < len(plan.specs) - 1:
                workflow.add_edge(spec.clear_node, plan.specs[i + 1].agent_node)
            else:
                workflow.add_edge(spec.clear_node, "Bull Researcher")

        workflow.add_conditional_edges(
            "Bull Researcher",
            self.conditional_logic.should_continue_debate,
            {"Bear Researcher": "Bear Researcher", "Research Manager": "Research Manager"},
        )
        workflow.add_conditional_edges(
            "Bear Researcher",
            self.conditional_logic.should_continue_debate,
            {"Bull Researcher": "Bull Researcher", "Research Manager": "Research Manager"},
        )
        workflow.add_edge("Research Manager", "Trader")
        workflow.add_edge("Trader", "Aggressive Analyst")
        workflow.add_conditional_edges(
            "Aggressive Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {"Conservative Analyst": "Conservative Analyst", "Portfolio Manager": "Portfolio Manager"},
        )
        workflow.add_conditional_edges(
            "Conservative Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {"Neutral Analyst": "Neutral Analyst", "Portfolio Manager": "Portfolio Manager"},
        )
        workflow.add_conditional_edges(
            "Neutral Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {"Aggressive Analyst": "Aggressive Analyst", "Portfolio Manager": "Portfolio Manager"},
        )
        workflow.add_edge("Portfolio Manager", END)

        return workflow


class OptimizedTradingAgentsGraph(TradingAgentsGraph):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.graph_setup = OptimizedGraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.tool_nodes,
            self.conditional_logic,
            analyst_concurrency_limit=self.config.get("analyst_concurrency_limit", 1),
        )
        self.workflow = self.graph_setup.setup_graph(
            kwargs.get("selected_analysts", ["governance", "market", "news", "fundamentals"])
        )
        self.graph = self.workflow.compile()


# ═════════════════════════════════════════════════════════════════════════════
# TradingAgents Configuration
# ═════════════════════════════════════════════════════════════════════════════


def build_ta_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    # Tier 1 (bulk agent nodes): DeepSeek V4 Flash via OpenAI-compatible API
    # Tier 2 (Research Manager, Portfolio Manager): Claude Haiku 4.5
    config["llm_provider"] = "deepseek"  # global fallback
    config["deep_think_llm"] = HAIKU_MODEL  # Research Manager + Portfolio Manager
    config["deep_think_provider"] = "anthropic"  # Force Anthropic for Haiku
    config["quick_think_llm"] = DEEPSEEK_MODEL  # Market/News/Fundamentals/Bull/Bear/Trader/Debaters
    config["quick_think_provider"] = "deepseek"  # Force DeepSeek for V4 Flash
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1
    config["max_tokens"] = 4000
    return config


def run_trading_agents(full_ticker: str, analysis_date: str) -> str:
    print(f"\n[AI] Initializing Analysis for {full_ticker}...")
    print(f"[AI] Thinking: Gathering market data and fundamental ratios...")
    config = build_ta_config()
    ta = OptimizedTradingAgentsGraph(
        selected_analysts=["governance", "market", "news", "fundamentals"],
        debug=True,  # Enable debug for terminal logs
        config=config,
    )
    print(f"[AI] Thinking: Running Agent Graph propagation...")
    final_state, decision = ta.propagate(full_ticker, analysis_date)
    print(f"[AI] Thinking: Analysis complete. Formatting output...")
    governance_report = final_state.get("governance_report", "")
    output = str(decision)
    if governance_report:
        output = f"GOVERNANCE FORENSICS REPORT:\n{governance_report}\n\n---\n\n{output}"
    return output


# ═════════════════════════════════════════════════════════════════════════════
# Reformat with Claude (Phase 1) → DeepSeek V4 Flash fallback (Phase 2)
# ═════════════════════════════════════════════════════════════════════════════


def reformat_with_claude(
    raw_output: str,
    full_ticker: str,
    exchange: str,
    prior_analyses: list[dict] | None = None,
) -> dict:
    """Reformat raw AI output into structured JSON.
    Tries Claude Sonnet first, falls back to DeepSeek V4 Flash if Claude fails,
    then applies _normalize_response to guarantee iOS-safe output.
    """
    import json
    import time

    # Deterministic serialization for breakpoint 2
    serialized_history = ""
    if prior_analyses:
        history_points = []
        for p in prior_analyses[-15:]:
            history_points.append(
                {
                    "date": p.get("analysis_date"),
                    "signal": p.get("signal"),
                    "conf": p.get("confidence_pct"),
                    "target_3m": p.get("target_prices", {}).get("short_term_3m"),
                }
            )
        serialized_history = json.dumps(history_points, sort_keys=True)

    system_prompt = INDIAN_MARKET_SYSTEM_PROMPT
    if serialized_history:
        system_prompt += (
            f"\n\nPREVIOUS HISTORICAL ANALYSES (CONTEXT):\n{serialized_history}"
        )

    user_message = (
        f"Below is the raw trading analysis for {full_ticker} ({exchange}).\n\n"
        f"<raw_analysis>\n{raw_output}\n</raw_analysis>\n\n"
        f"Today's date: {date.today().strftime('%d-%b-%Y')}"
    )

    def _validate_parsed(parsed: dict) -> dict | None:
        """Check parsed JSON has minimum required fields."""
        if not isinstance(parsed, dict):
            return None
        if not parsed.get("signal"):
            return None
        kf = parsed.get("key_factors", {})
        if not kf.get("indian_market_sentiment", "").strip():
            kf["indian_market_sentiment"] = (
                "Sentiment data not available for this stock."
            )
            parsed["key_factors"] = kf
        return parsed

    # ── Phase 1: Claude Sonnet ────────────────────────────────────────────
    claude_api_key = os.getenv("ANTHROPIC_API_KEY")
    claude_succeeded = False
    if claude_api_key:
        claude_client = anthropic.Anthropic(api_key=claude_api_key)
        system_array = [
            {
                "type": "text",
                "text": INDIAN_MARKET_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        if serialized_history:
            system_array.append(
                {
                    "type": "text",
                    "text": f"PREVIOUS HISTORICAL ANALYSES (CONTEXT):\n{serialized_history}",
                    "cache_control": {"type": "ephemeral"},
                }
            )

        for attempt in range(3):
            try:
                response = claude_client.messages.create(
                    model=SONNET_MODEL,
                    max_tokens=4000,
                    system=system_array,
                    messages=[{"role": "user", "content": user_message}],
                    temperature=0,
                    extra_body={"cache_control": {"type": "ephemeral"}},
                )
                _log_token_usage("reformat", response.usage)
                raw_json = _extract_json_from_text(response.content[0].text)
                parsed = json.loads(raw_json)
                validated = _validate_parsed(parsed)
                if validated is not None:
                    return validated
                print(
                    f"[WARN] Claude returned partial JSON, falling through to DeepSeek"
                )
                break
            except Exception as e:
                err_msg = str(e).lower()
                is_cache_eviction = any(kw in err_msg for kw in (
                    "cache_expired", "ephemeral", "prompt_cache",
                    "cache_not_found", "evicted",
                ))
                print(f"[Anthropic] Reformat attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    # Fix 2.35: cache eviction errors get extended backoff
                    # to stay under the 1200s gateway timeout while cache repopulates
                    backoff = 4.0 * (2 ** attempt) if is_cache_eviction else 1.0 * (2 ** attempt)
                    if is_cache_eviction:
                        print("[Anthropic] Cache eviction detected — extended backoff")
                    time.sleep(backoff)

    # ── Phase 2: DeepSeek V4 Flash fallback ──────────────────────────────
    if os.getenv("DEEPSEEK_API_KEY"):
        print(f"[DeepSeek] Reformatting {full_ticker} via DeepSeek V4 Flash...")
        ds_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        try:
            ds_raw = _deepseek_chat(
                ds_messages,
                max_tokens=4000,
                temperature=0,
                log_endpoint="reformat_deepseek",
            )
            raw_json = _extract_json_from_text(ds_raw)
            parsed = json.loads(raw_json)
            validated = _validate_parsed(parsed)
            if validated is not None:
                return validated
        except Exception as e:
            print(f"[DeepSeek] Reformating failed: {e}")

    # ── Phase 3: Ultimate fallback ────────────────────────────────────────
    print(f"[FALLBACK] Returning normalized minimal analysis for {full_ticker}")
    return _normalize_response(
        {
            "ticker": full_ticker,
            "company_name": full_ticker,
            "exchange": exchange,
            "analysis_date": date.today().strftime("%Y-%m-%d"),
            "signal": "HOLD",
            "confidence_pct": 0,
            "current_price_inr": 0.0,
            "target_prices": {},
            "upside_downside_pct": {},
            "bull_case": [],
            "bear_case": [],
            "key_risks": [],
            "what_to_watch": [],
            "key_factors": {},
            "fundamentals_snapshot": {},
            "disclaimer": "Analysis failed due to an API error. Please try again later.",
            "confidence_rationale": "Analysis could not be completed due to an API error.",
            "raw_output": raw_output,
        }
    )


# ═════════════════════════════════════════════════════════════════════════════
# Response Normalization — guarantee iOS-safe types
# ═════════════════════════════════════════════════════════════════════════════


_SIGNAL_MAP = {
    "BUY": "BULLISH",
    "STRONG BUY": "BULLISH",
    "STRONG_BUY": "BULLISH",
    "SELL": "BEARISH",
    "STRONG SELL": "BEARISH",
    "STRONG_SELL": "BEARISH",
    "AVOID": "BEARISH",
    "CAUTIOUS": "CAUTIOUSLY BEARISH",
    # Complex advisory ratings — preserve granularity instead of flattening to HOLD
    "ACCUMULATE": "CAUTIOUSLY BULLISH",
    "ACCUMULATE ON DIPS": "CAUTIOUSLY BULLISH",
    "REDUCE": "CAUTIOUSLY BEARISH",
    "REDUCE ON RALLIES": "CAUTIOUSLY BEARISH",
    "BOOK PROFIT": "CAUTIOUSLY BEARISH",
    "BOOK PROFITS": "CAUTIOUSLY BEARISH",
    "EXIT": "BEARISH",
    "ADD": "CAUTIOUSLY BULLISH",
    "BUY ON DIPS": "BULLISH",
    "SELL ON RALLIES": "BEARISH",
}


def _sanitize_nan_inf(obj):
    """Recursively replace NaN/Inf/-Inf with None (JSON null) in dicts/lists.
    Prevents Swift JSONDecoder failures from invalid float values.
    """
    import math as _m
    if isinstance(obj, dict):
        return {k: _sanitize_nan_inf(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_nan_inf(v) for v in obj]
    if isinstance(obj, float) and (_m.isnan(obj) or _m.isinf(obj)):
        return None
    return obj


def _normalize_response(result: dict) -> dict:
    """Sanitize AI analysis response to ensure all iOS-required fields exist with correct types.
    Handles null values, missing fields, type mismatches, NaN/Inf->null, and float->int coercion.
    """
    import math

    # 0. Clean NaN/Inf values before any other processing
    result = _sanitize_nan_inf(result)

    # 1. Signal normalization
    if "signal" in result:
        normalized = result["signal"].strip().upper()
        result["signal"] = _SIGNAL_MAP.get(normalized, normalized)

    # 2. confidence_pct — must be int (iOS decodes as Int)
    try:
        result["confidence_pct"] = int(float(result.get("confidence_pct", 0)))
    except (ValueError, TypeError, OverflowError):
        result["confidence_pct"] = 0

    # 3. current_price_inr — must be float
    try:
        result["current_price_inr"] = float(result.get("current_price_inr", 0))
    except (ValueError, TypeError):
        result["current_price_inr"] = 0.0

    # 4. target_prices — all three must be non-null float
    tp = result.get("target_prices")
    if not isinstance(tp, dict):
        tp = {}
        result["target_prices"] = tp
    for key in ("short_term_3m", "medium_term_12m", "long_term_36m"):
        val = tp.get(key)
        try:
            v = float(val) if val is not None else 0.0
            tp[key] = 0.0 if math.isnan(v) or math.isinf(v) else v
        except (ValueError, TypeError):
            tp[key] = 0.0

    # 5. upside_downside_pct — all three must be non-null float
    ud = result.get("upside_downside_pct")
    if not isinstance(ud, dict):
        ud = {}
        result["upside_downside_pct"] = ud
    for key in ("short_term", "medium_term", "long_term"):
        val = ud.get(key)
        try:
            v = float(val) if val is not None else 0.0
            ud[key] = 0.0 if math.isnan(v) or math.isinf(v) else v
        except (ValueError, TypeError):
            ud[key] = 0.0

    # 6. Array fields — must be non-null list
    for arr_key in ("bull_case", "bear_case", "key_risks", "what_to_watch"):
        if not isinstance(result.get(arr_key), list):
            result[arr_key] = []

    # 7. key_factors — all required fields must be non-empty string
    kf = result.get("key_factors")
    if not isinstance(kf, dict):
        kf = {}
        result["key_factors"] = kf
    for key in (
        "management_quality",
        "geopolitical_context",
        "promoter_fii_dii_activity",
        "governance_assessment",
        "turnaround_story",
        "fundamentals_summary",
        "global_macro_impact",
        "news_sentiment",
        "indian_market_sentiment",
    ):
        val = kf.get(key)
        if not isinstance(val, str) or not val.strip():
            kf[key] = "Data not available"

    # 8. disclaimer — must be non-empty string
    if (
        not isinstance(result.get("disclaimer"), str)
        or not result["disclaimer"].strip()
    ):
        result["disclaimer"] = (
            "This is an AI-generated analysis. Do your own research before investing."
        )

    # 9. ticker — must be non-empty string
    if not isinstance(result.get("ticker"), str) or not result["ticker"].strip():
        result["ticker"] = str(result.get("company_name", "UNKNOWN"))

    # 10. exchange — must be non-empty string (iOS decodes as non-optional)
    if (
        not isinstance(result.get("exchange"), str)
        or not result["exchange"].strip()
    ):
        result["exchange"] = "NSE"

    # 11. company_name — must be non-empty string
    if (
        not isinstance(result.get("company_name"), str)
        or not result["company_name"].strip()
    ):
        result["company_name"] = str(result.get("ticker", "Unknown"))

    # 13. fundamentals_snapshot — must be dict (iOS decodes as non-optional)
    if not isinstance(result.get("fundamentals_snapshot"), dict):
        result["fundamentals_snapshot"] = {}

    # 14. governance fields — must be present (governance analyst output)
    if not isinstance(result.get("governance_score"), (int, float)):
        result["governance_score"] = 0
    if not isinstance(result.get("governance_red_flags"), list):
        result["governance_red_flags"] = []

    # 15. analysis_date — must be string
    if not isinstance(result.get("analysis_date"), str):
        from datetime import date

        result["analysis_date"] = date.today().strftime("%Y-%m-%d")

    return result


# ═════════════════════════════════════════════════════════════════════════════
# Main Analysis Orchestrator
# ═════════════════════════════════════════════════════════════════════════════

def _inject_piotroski(result: dict, ticker: str):
    try:
        from services.piotroski import compute_piotroski
        pio = compute_piotroski(ticker.upper())
        result["piotroski_score"] = pio.get("f_score")
        result["piotroski_flags"] = pio.get("checks", {})
    except Exception:
        result["piotroski_score"] = None
        result["piotroski_flags"] = {}


def _inject_live_data(result: dict, ticker: str) -> dict:
    """Refresh current price, recent news, and 3M/6M/12M price performance.
    Called on every return path so cached reports never show stale market data.
    """
    ns_ticker = _to_ns(ticker)

    # 1. Current price — always fetch live
    try:
        curr_p, _ = _yf_price(ns_ticker)
        if curr_p:
            result["current_price_inr"] = float(curr_p)
    except Exception as e:
        print(f"[LIVE_DATA] Price refresh failed for {ticker}: {e}")

    # 2. Recent news — DB first, yfinance fallback
    try:
        with get_session() as session:
            articles = (
                session.query(NewsArticle)
                .filter(
                    NewsArticle.ticker == ticker.upper(),
                    NewsArticle.published_at >= datetime.utcnow() - timedelta(days=7),
                )
                .order_by(NewsArticle.published_at.desc())
                .limit(8)
                .all()
            )
            recent_news = [
                {
                    "title": a.headline,
                    "publisher": a.source,
                    "link": a.article_url,
                    "publish_time": int(a.published_at.timestamp()) if a.published_at else 0,
                    "summary": a.summary or "",
                    "image_url": a.image_url,
                }
                for a in articles
            ]

        if not recent_news:
            raw = (yf.Ticker(ns_ticker).news or [])[:8]
            for item in raw:
                content = item.get("content", {})
                pub = content.get("pubDate") or item.get("providerPublishTime", 0)
                if isinstance(pub, str):
                    try:
                        pub = int(datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp())
                    except Exception:
                        pub = 0
                recent_news.append({
                    "title": content.get("title") or item.get("title", ""),
                    "publisher": content.get("provider", {}).get("displayName") or item.get("publisher", ""),
                    "link": content.get("canonicalUrl", {}).get("url") or item.get("link", ""),
                    "publish_time": int(pub) if pub else 0,
                    "summary": content.get("summary") or "",
                    "image_url": None,
                })

        if recent_news:
            result["recent_news"] = recent_news
    except Exception as e:
        print(f"[LIVE_DATA] News refresh failed for {ticker}: {e}")

    # 3. Price performance — 3M / 6M / 12M % change
    try:
        hist = yf.Ticker(ns_ticker).history(period="1y")
        if not hist.empty:
            curr_close = float(hist["Close"].iloc[-1])

            def _chg(days: int):
                cutoff = hist.index[-1] - timedelta(days=days)
                past = hist[hist.index <= cutoff]
                if past.empty:
                    return None
                p = float(past["Close"].iloc[-1])
                return round((curr_close - p) / p * 100, 2) if p else None

            result["price_performance"] = {
                "change_3m_pct":  _chg(90),
                "change_6m_pct":  _chg(182),
                "change_12m_pct": _chg(365),
            }
    except Exception as e:
        print(f"[LIVE_DATA] Price performance fetch failed for {ticker}: {e}")

    return result

def analyze(
    ticker: str,
    exchange: str,
    user_id: int | None = None,
    deep_scan: bool = False,
) -> dict:
    exchange = exchange.upper()
    if exchange not in EXCHANGE_SUFFIX:
        raise ValueError(f"Unsupported exchange: {exchange}. Use NSE or BSE.")
    full_ticker = _resolve_ticker(ticker, exchange)
    analysis_date = date.today().strftime("%Y-%m-%d")

    # Fix 2.38: Generate anonymous session hash for unauthenticated requests.
    # Prevents duplicate LLM cycles from the same public session.
    if user_id is None:
        import hashlib as _hl
        _anon_key = f"{full_ticker}|{analysis_date}|public"
        user_id = abs(hash(_anon_key)) % (10 ** 8)

    with get_session() as session:
        # 1. Query Cache: Check global history for today
        cached_today = get_analysis_for_date(session, ticker, analysis_date)
        if cached_today:
            print(
                f"[CACHE HIT] Returning existing analysis for {full_ticker} on {analysis_date}"
            )
            cached_today = _normalize_response(cached_today)
            cached_today["ticker"] = ticker.upper()
            cached_today["exchange"] = exchange
            cached_today["_cache_type"] = "CACHE HIT"
            if user_id:
                user_has_it = (
                    session.query(AnalysisHistory)
                    .filter_by(
                        user_id=user_id,
                        ticker=ticker.upper(),
                        analysis_date=analysis_date,
                    )
                    .first()
                )
                if not user_has_it:
                    try:
                        cached_today = save_analysis(
                            session,
                            user_id,
                            ticker.upper(),
                            cached_today,
                            raw_output=cached_today.get("raw_output"),
                        )
                    except Exception as _cache_save_err:
                        print(
                            f"[WARN] Cache hit save_analysis failed for {ticker}: {_cache_save_err}"
                        )
            from datetime import timezone as _tz

            _cutoff = datetime.now(_tz.utc).replace(tzinfo=None) - timedelta(days=14)
            _advisor_rows = (
                session.query(AdvisorInsight)
                .filter(
                    AdvisorInsight.ticker == ticker.upper(),
                    AdvisorInsight.published_at >= _cutoff,
                )
                .order_by(AdvisorInsight.published_at.desc())
                .limit(10)
                .all()
            )
            cached_today["advisor_matrix"] = [
                {
                    "advisor_name": r.advisor_name,
                    "stance": r.stance,
                    "confidence": r.confidence,
                    "catalyst_summary": r.catalyst_summary,
                    "video_title": r.video_title,
                    "video_url": r.video_url,
                    "published_at": (
                        r.published_at.isoformat() if r.published_at else None
                    ),
                    "transcript_source": r.transcript_source,
                }
                for r in _advisor_rows
            ]
            cached_today["deep_scan_used"] = False
            cached_today["pkscreener_signals"] = None
            _inject_piotroski(cached_today, ticker)
            cached_today = _inject_live_data(cached_today, ticker)
            return cached_today

        # 2. Fetch deep history for AI context
        prior = get_all_ticker_history(session, ticker, user_id)

    # 3. Smart Cache: Check if news warrants a new expensive analysis
    if prior:
        last_analysis = prior[-1]
        last_date_str = last_analysis.get("analysis_date")
        if last_date_str != analysis_date:
            try:
                ns_ticker = _to_ns(ticker)
                t = yf.Ticker(ns_ticker)
                recent_news = t.news[:5] if t.news else []
                if recent_news:
                    print(
                        f"[AI] Thinking: Fast-checking recent news to see if full analysis is needed..."
                    )
                    news_text = "\n".join(
                        [f"- {n.get('title', '')}" for n in recent_news]
                    )

                    # Fix 2.19: check for special dividends/bonus/splits in headlines
                    # before Smart Cache Gate — these are ALWAYS major fundamental shifts
                    import re as _cache_re
                    _force_refresh_patterns = [
                        r"special\s+dividend",
                        r"bonus\s+(?:issue|share)",
                        r"stock\s+split",
                        r"rights\s+issue",
                        r"buyback",
                        r"delisting",
                    ]
                    _force_refresh = any(
                        _cache_re.search(p, news_text, _cache_re.IGNORECASE)
                        for p in _force_refresh_patterns
                    )

                    # Smart cache gate → DeepSeek V4 Flash (Tier 1 bulk task)
                    if os.getenv("DEEPSEEK_API_KEY") and not _force_refresh:
                        prompt = (
                            f"Stock: {full_ticker}\nLast analysis date: {last_date_str}\n"
                            f"Recent News Headlines:\n{news_text}\n\n"
                            "Based ONLY on these headlines, has there been a major fundamental "
                            f"shift, severe shock, or significant trend-changing event for this "
                            f"company since {last_date_str}? Answer strictly with a single word: 'YES' or 'NO'."
                        )
                        answer = (
                            _deepseek_chat(
                                [{"role": "user", "content": prompt}],
                                max_tokens=10,
                                temperature=0,
                                log_endpoint="smart_cache",
                            )
                            .strip()
                            .upper()
                        )

                        if "NO" in answer:
                            print(
                                f"[SMART CACHE] No major news changes for {full_ticker} since {last_date_str}. Reusing previous report to save credits."
                            )
                            import copy

                            new_analysis = copy.deepcopy(last_analysis)
                            new_analysis["analysis_date"] = analysis_date

                            new_analysis = _normalize_response(new_analysis)
                            new_analysis["ticker"] = ticker.upper()
                            new_analysis["exchange"] = exchange
                            new_analysis["_cache_type"] = "SMART CACHE"
                            try:
                                with get_session() as session:
                                    new_analysis = save_analysis(
                                        session,
                                        user_id,
                                        ticker.upper(),
                                        new_analysis,
                                        raw_output=new_analysis.get("raw_output"),
                                    )
                                    from datetime import timezone as _tz

                                    _cutoff = datetime.now(_tz.utc).replace(
                                        tzinfo=None
                                    ) - timedelta(days=14)
                                    _advisor_rows = (
                                        session.query(AdvisorInsight)
                                        .filter(
                                            AdvisorInsight.ticker == ticker.upper(),
                                            AdvisorInsight.published_at >= _cutoff,
                                        )
                                        .order_by(AdvisorInsight.published_at.desc())
                                        .limit(10)
                                        .all()
                                    )
                            except Exception as _save_err:
                                print(
                                    f"[WARN] Smart cache save_analysis failed for {ticker}: {_save_err}"
                                )
                                _advisor_rows = []
                            new_analysis["advisor_matrix"] = [
                                {
                                    "advisor_name": r.advisor_name,
                                    "stance": r.stance,
                                    "confidence": r.confidence,
                                    "catalyst_summary": r.catalyst_summary,
                                    "video_title": r.video_title,
                                    "video_url": r.video_url,
                                    "published_at": (
                                        r.published_at.isoformat()
                                        if r.published_at
                                        else None
                                    ),
                                    "transcript_source": r.transcript_source,
                                }
                                for r in _advisor_rows
                            ]
                            new_analysis["deep_scan_used"] = False
                            new_analysis["pkscreener_signals"] = None
                            new_analysis = _inject_live_data(new_analysis, ticker)
                            return new_analysis
                        else:
                            print(
                                f"[AI] Thinking: News indicates possible changes ({answer}). Proceeding with full deep analysis."
                            )
            except Exception as e:
                print(
                    f"[AI] Smart cache news check failed: {e}. Defaulting to full analysis."
                )

    print(f"[CACHE MISS] Generating new deep analysis for {full_ticker}...")

    # Fetch pledging info for AI context
    pledging_data = "Unavailable"
    try:
        ns_ticker = _to_ns(ticker)
        inf = _yf_fetch_info(ns_ticker)
        # Search for any key that might be pledging
        p_keys = [k for k in inf.keys() if "pledge" in k.lower()]
        if p_keys:
            pledging_data = f"{inf[p_keys[0]]}%"
        else:
            # Try to get from major_holders if available
            try:
                mh = yf.Ticker(ns_ticker).major_holders
                if "pledged" in str(mh).lower():
                    pledging_data = str(mh)
            except:
                pass
    except:
        pass

    raw_output = run_trading_agents(full_ticker, analysis_date)
    raw_output += f"\n\nADDITIONAL DATA (MANDATORY TO INCLUDE IN fundamentals_snapshot):\nPromoter Pledging: {pledging_data}\n"

    # ── Deep Scan: PKScreener + FinBERT injection ────────────────────────────
    pk_signal = None
    deep_scan_used = False
    if deep_scan:
        deep_scan_used = True
        try:
            with get_session() as session:
                pk_signal = (
                    session.query(PKScreenerSignal)
                    .filter(PKScreenerSignal.ticker == ticker.upper())
                    .order_by(PKScreenerSignal.signal_date.desc())
                    .first()
                )

            if pk_signal:
                pkscreener_context = f"""
PKSCREENER TECHNICAL PRE-SCAN (as of {pk_signal.signal_date}):
- Technical Score: {pk_signal.technical_score:.2f}/1.00 (0=Strong Sell, 1=Strong Buy)
- Breakout Detected: {pk_signal.breakout}
- Consolidating: {pk_signal.consolidating}
- RSI: {pk_signal.rsi if pk_signal.rsi else 'N/A'}
- MACD Signal: {pk_signal.macd_signal or 'N/A'}
- Moving Average Position: {pk_signal.ma_signal or 'N/A'}
- Volume Signal: {pk_signal.volume_signal or 'N/A'}
- Chart Pattern: {pk_signal.pattern or 'None detected'}

Use this PKScreener data as an additional technical anchor. It does NOT override your
own technical analysis — treat it as a corroborating or conflicting data point.
If your RSI calculation differs from PKScreener's, note the divergence explicitly.
"""
                raw_output += f"\n\n{pkscreener_context}"
        except Exception as e:
            print(f"[DEEP-SCAN] PKScreener context fetch failed: {e}")

        # FinBERT sentiment context
        try:
            from services.sentiment_engine import score_article

            with get_session() as session:
                recent_news = (
                    session.query(NewsArticle)
                    .filter(
                        NewsArticle.ticker == ticker.upper(),
                        NewsArticle.published_at
                        >= datetime.utcnow() - timedelta(days=7),
                    )
                    .order_by(NewsArticle.published_at.desc())
                    .limit(5)
                    .all()
                )

                if recent_news:
                    scored_lines = []
                    for article in recent_news:
                        score = article.sentiment_score
                        label = article.sentiment_label
                        if score is None:
                            label, score = score_article(
                                article.headline, article.summary
                            )
                        scored_lines.append(
                            f"  [{score:+.2f} {label}] {article.headline[:80]}"
                        )
                    finbert_context = (
                        "FINBERT NEWS SENTIMENT (last 7 days):\n"
                        + "\n".join(scored_lines)
                        + "\nUse these scores as a sentiment anchor. Positive = tailwind, Negative = headwind."
                    )
                    raw_output += f"\n\n{finbert_context}"
        except Exception as e:
            print(f"[DEEP-SCAN] FinBERT context build failed: {e}")

    result = reformat_with_claude(
        raw_output, full_ticker, exchange, prior_analyses=prior
    )
    result = _normalize_response(result)
    result["ticker"] = ticker.upper()
    result["exchange"] = exchange
    result["_cache_type"] = "FULL AI"

    try:
        with get_session() as session:
            result = save_analysis(
                session,
                user_id,
                ticker.upper(),
                result,
                raw_output=raw_output,
            )
            from datetime import timezone as _tz

            _cutoff = datetime.now(_tz.utc).replace(tzinfo=None) - timedelta(days=14)
            _advisor_rows = (
                session.query(AdvisorInsight)
                .filter(
                    AdvisorInsight.ticker == ticker.upper(),
                    AdvisorInsight.published_at >= _cutoff,
                )
                .order_by(AdvisorInsight.published_at.desc())
                .limit(10)
                .all()
            )
    except Exception as e:
        print(
            f"[WARN] save_analysis failed for {ticker}, returning result anyway: {e}"
        )
        _advisor_rows = []
    result["advisor_matrix"] = [
        {
            "advisor_name": r.advisor_name,
            "stance": r.stance,
            "confidence": r.confidence,
            "catalyst_summary": r.catalyst_summary,
            "video_title": r.video_title,
            "video_url": r.video_url,
            "published_at": r.published_at.isoformat() if r.published_at else None,
            "transcript_source": r.transcript_source,
        }
        for r in _advisor_rows
    ]

    # Add deep scan metadata
    result["deep_scan_used"] = deep_scan_used
    if pk_signal:
        result["pkscreener_signals"] = {
            "technical_score": pk_signal.technical_score,
            "breakout": pk_signal.breakout,
            "rsi": pk_signal.rsi,
            "ma_signal": pk_signal.ma_signal,
            "pattern": pk_signal.pattern,
            "signal_date": pk_signal.signal_date,
        }
    else:
        result["pkscreener_signals"] = None

    _inject_piotroski(result, ticker)
    result = _inject_live_data(result, ticker)
    return result
