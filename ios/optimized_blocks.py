import os
import json
import hashlib
import time
import io
from datetime import date, datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
import multiprocessing
import asyncio
from fastapi import Request
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import anthropic
import yfinance as yf

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage, MessagesPlaceholder
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END

try:
    import openpyxl
    from openpyxl.styles import PatternFill, Font as XLFont, Alignment
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from prompts import INDIAN_MARKET_SYSTEM_PROMPT
from database import init_db, get_session, save_analysis, get_recent_analyses, get_user_by_credentials, Portfolio, User, AnalysisHistory, get_analysis_for_date, get_all_ticker_history, PriceTarget

# Import specific agent factories and states from core
from tradingagents.agents import create_bull_researcher, create_bear_researcher, create_research_manager, create_trader, create_aggressive_debator, create_neutral_debator, create_conservative_debator, create_portfolio_manager, create_msg_delete
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.graph.analyst_execution import build_analyst_execution_plan
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.setup import GraphSetup
from tradingagents.agents.utils.agent_utils import get_instrument_context_from_state

load_dotenv()

# Model Identifiers
HAIKU_MODEL = "claude-3-5-haiku-20241022"
SONNET_MODEL = "claude-3-5-sonnet-latest"

# ---------------------------------------------------------------------------
# Constants: Prompt Caching Blocks
# ---------------------------------------------------------------------------

BASE_INSTITUTIONAL_INSTRUCTION = """You are a helpful AI assistant, collaborating with other assistants. Use the provided tools to progress towards answering the question. If you are unable to fully answer, that's OK; another assistant with different tools will help where you left off. Execute what you can to make progress. If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable, prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."""

MARKET_ANALYST_PERSONA = """You are a trading assistant tasked with analyzing financial markets. Your role is to select the **most relevant indicators** for a given market condition or trading strategy from the following list. The goal is to choose up to **8 indicators** that provide complementary insights without redundancy.

Indicators:
- close_50_sma, close_200_sma, close_10_ema (Moving Averages)
- macd, macds, macdh (Momentum)
- rsi (Momentum)
- boll, boll_ub, boll_lb (Volatility)
- atr (Volatility)
- vwma (Volume)

Tool Definitions:
- get_stock_data(symbol, start_date, end_date): Retrieve OHLCV price data.
- get_indicators(symbol, indicator, curr_date, look_back_days): Get specific technical indicators.
- get_verified_market_snapshot(symbol, date): Source of truth for exact price/indicator values.

Write a very detailed and nuanced report. Append a Markdown table for key points."""

NEWS_ANALYST_PERSONA = """You are a news researcher tasked with analyzing recent news and trends over the past week. Write a comprehensive report of the current state of the world relevant for trading and macroeconomics. 

Tool Definitions:
- get_news(ticker, start_date, end_date): Ticker-specific news.
- get_global_news(curr_date, look_back_days, limit): Macroeconomic news.
- get_insider_transactions(ticker): Insider trades and disclosures.

Write a comprehensive report with actionable insights. Append a Markdown table for key points."""

FUNDAMENTALS_ANALYST_PERSONA = """You are a researcher tasked with analyzing fundamental information. Write a comprehensive report on the company's financials (balance sheet, cash flow, income statement) and profile to gain a full view for traders.

Tool Definitions:
- get_fundamentals(ticker, curr_date): Comprehensive fundamental summary.
- get_balance_sheet(ticker, freq, curr_date): Balance sheet details.
- get_cashflow(ticker, freq, curr_date): Cash flow details.
- get_income_statement(ticker, freq, curr_date): Income statement details.

Provide specific, actionable insights. Append a Markdown table for key points."""

# ---------------------------------------------------------------------------
# Optimized Analyst Node Factory
# ---------------------------------------------------------------------------

def create_optimized_analyst_node(llm, analyst_type: str, persona: str, report_key: str, tools: list):
    def analyst_node(state):
        instrument_context = get_instrument_context_from_state(state)
        current_date = state["trade_date"]
        
        # Phase 1: Separate static instructions (cached) from volatile data (human message)
        static_system_block = f"{BASE_INSTITUTIONAL_INSTRUCTION}\n\n{persona}\n\nYou have access to the following tools: {', '.join([t.name for t in tools])}."
        
        # Payload construction with cache tag
        # We use a human message for the volatile ticker/date context to keep system prompt stable
        volatile_context = f"The current trading date is {current_date}. {instrument_context}"
        
        # Anthropic prompt caching via message structure
        messages = [
            SystemMessage(content=[
                {
                    "type": "text", 
                    "text": static_system_block,
                    "cache_control": {"type": "ephemeral"}
                }
            ]),
            MessagesPlaceholder(variable_name="messages"),
            HumanMessage(content=volatile_context)
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

# ---------------------------------------------------------------------------
# Optimized Graph Setup
# ---------------------------------------------------------------------------

class OptimizedGraphSetup(GraphSetup):
    def setup_graph(self, selected_analysts=["market", "news", "fundamentals"]):
        from tradingagents.agents.utils.agent_utils import (
            get_stock_data, get_indicators, get_news, get_global_news, 
            get_insider_transactions, get_fundamentals, get_balance_sheet, 
            get_cashflow, get_income_statement
        )
        
        plan = build_analyst_execution_plan(selected_analysts, concurrency_limit=self.analyst_concurrency_limit)
        
        # Define optimized analyst factories
        analyst_factories = {
            "market": lambda: create_optimized_analyst_node(
                self.quick_thinking_llm, "market", MARKET_ANALYST_PERSONA, "market",
                [get_stock_data, get_indicators]
            ),
            "news": lambda: create_optimized_analyst_node(
                self.quick_thinking_llm, "news", NEWS_ANALYST_PERSONA, "news",
                [get_news, get_global_news, get_insider_transactions]
            ),
            "fundamentals": lambda: create_optimized_analyst_node(
                self.quick_thinking_llm, "fundamentals", FUNDAMENTALS_ANALYST_PERSONA, "fundamentals",
                [get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement]
            ),
            "social": lambda: create_optimized_analyst_node(
                self.quick_thinking_llm, "social", "You are a sentiment analyst.", "sentiment", [get_news]
            )
        }

        # Rest of the nodes from core
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
            workflow.add_conditional_edges(spec.agent_node, getattr(self.conditional_logic, f"should_continue_{spec.key}"), [spec.tool_node, spec.clear_node])
            workflow.add_edge(spec.tool_node, spec.agent_node)
            if i < len(plan.specs) - 1:
                workflow.add_edge(spec.clear_node, plan.specs[i+1].agent_node)
            else:
                workflow.add_edge(spec.clear_node, "Bull Researcher")

        workflow.add_conditional_edges("Bull Researcher", self.conditional_logic.should_continue_debate, {"Bear Researcher": "Bear Researcher", "Research Manager": "Research Manager"})
        workflow.add_conditional_edges("Bear Researcher", self.conditional_logic.should_continue_debate, {"Bull Researcher": "Bull Researcher", "Research Manager": "Research Manager"})
        workflow.add_edge("Research Manager", "Trader")
        workflow.add_edge("Trader", "Aggressive Analyst")
        workflow.add_conditional_edges("Aggressive Analyst", self.conditional_logic.should_continue_risk_analysis, {"Conservative Analyst": "Conservative Analyst", "Portfolio Manager": "Portfolio Manager"})
        workflow.add_conditional_edges("Conservative Analyst", self.conditional_logic.should_continue_risk_analysis, {"Neutral Analyst": "Neutral Analyst", "Portfolio Manager": "Portfolio Manager"})
        workflow.add_conditional_edges("Neutral Analyst", self.conditional_logic.should_continue_risk_analysis, {"Aggressive Analyst": "Aggressive Analyst", "Portfolio Manager": "Portfolio Manager"})
        workflow.add_edge("Portfolio Manager", END)

        return workflow

class OptimizedTradingAgentsGraph(TradingAgentsGraph):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Re-initialize GraphSetup with our Optimized version
        self.graph_setup = OptimizedGraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.tool_nodes,
            self.conditional_logic,
            analyst_concurrency_limit=self.config.get("analyst_concurrency_limit", 1),
        )
        self.workflow = self.graph_setup.setup_graph(kwargs.get("selected_analysts", ["market", "news", "fundamentals"]))
        self.graph = self.workflow.compile()

# ---------------------------------------------------------------------------
# Refactored Reformatter & API
# ---------------------------------------------------------------------------

def reformat_with_claude(
    raw_output: str,
    full_ticker: str,
    exchange: str,
    prior_analyses: list[dict] | None = None,
) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    # Deterministic serialization for breakpoint 2
    serialized_history = ""
    if prior_analyses:
        # Take last 15, sort keys for stable cache hash
        history_points = []
        for p in prior_analyses[-15:]:
            history_points.append({
                "date": p.get('analysis_date'),
                "signal": p.get('signal'),
                "conf": p.get('confidence_pct'),
                "target_3m": p.get('target_prices', {}).get('short_term_3m')
            })
        serialized_history = json.dumps(history_points, sort_keys=True)

    # EXECUTION PHASE 2: Dual-Breakpoint Cache Strategy
    system_array = [
        {
            "type": "text",
            "text": INDIAN_MARKET_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"} # Breakpoint 1: Static Blueprint
        }
    ]
    
    if serialized_history:
        system_array.append({
            "type": "text",
            "text": f"PREVIOUS HISTORICAL ANALYSES (CONTEXT):\n{serialized_history}",
            "cache_control": {"type": "ephemeral"} # Breakpoint 2: Ticker-specific Archives
        })

    user_message = f"Below is the raw trading analysis for {full_ticker} ({exchange}).\n\n<raw_analysis>\n{raw_output}\n</raw_analysis>\n\nToday's date: {date.today().strftime('%d-%b-%Y')}"

    response = client.messages.create(
        model=SONNET_MODEL,
        max_tokens=2000,
        system=system_array,
        messages=[{"role": "user", "content": user_message}],
        temperature=0 # Strict deterministic output
    )
    
    # Log token usage
    try:
        from main import _log_token_usage
        _log_token_usage("reformat", response.usage)
    except: pass

    raw_json = response.content[0].text.strip()
    if "```json" in raw_json:
        raw_json = raw_json.split("```json")[1].split("```")[0].strip()
    elif "```" in raw_json:
        raw_json = raw_json.split("```")[1].strip()

    return json.loads(raw_json)

def run_trading_agents(full_ticker: str, analysis_date: str) -> str:
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "anthropic"
    config["deep_think_llm"] = HAIKU_MODEL
    config["quick_think_llm"] = HAIKU_MODEL
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1
    config["max_tokens"] = 2000
    
    ta = OptimizedTradingAgentsGraph(
        selected_analysts=["market", "news", "fundamentals"],
        config=config,
    )
    _, decision = ta.propagate(full_ticker, analysis_date)
    return str(decision)
