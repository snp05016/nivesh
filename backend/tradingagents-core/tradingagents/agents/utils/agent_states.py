"""State definitions for the trading agents LangGraph.

This module defines the TypedDict structures used to maintain state
across different agent nodes during debate and analysis phases.
"""

from typing import Annotated, Optional
from typing_extensions import TypedDict
from langgraph.graph import MessagesState


# Researcher team state
class InvestDebateState(TypedDict):
    """State structure for the Bull vs Bear debate phase."""
    bull_history: Annotated[str, "Full history of Bull Analyst arguments"]
    bear_history: Annotated[str, "Full history of Bear Analyst arguments"]
    history: Annotated[str, "Full combined conversation history of the debate"]
    current_response: Annotated[str, "The most recent response in the debate"]
    latest_speaker: Annotated[str, "Identity of the researcher that spoke last"]
    judge_decision: Annotated[Optional[str], "The final decision made by the Research Manager"]
    count: Annotated[int, "Current round count of the debate"]


# Risk management team state
class RiskDebateState(TypedDict):
    """State structure for the Risk management discussion phase."""
    aggressive_history: Annotated[str, "Full history of Aggressive Analyst arguments"]
    conservative_history: Annotated[str, "Full history of Conservative Analyst arguments"]
    neutral_history: Annotated[str, "Full history of Neutral Analyst arguments"]
    history: Annotated[str, "Full combined conversation history of the risk debate"]
    latest_speaker: Annotated[str, "Identity of the agent that spoke last"]
    current_aggressive_response: Annotated[str, "Latest response by the Aggressive Analyst"]
    current_conservative_response: Annotated[str, "Latest response by the Conservative Analyst"]
    current_neutral_response: Annotated[str, "Latest response by the Neutral Analyst"]
    judge_decision: Annotated[Optional[str], "The final decision made by the Portfolio Manager"]
    count: Annotated[int, "Current round count of the risk discussion"]


class AgentState(MessagesState):
    """Main state definition for the trading agent graph."""
    company_of_interest: Annotated[str, "Ticker symbol of the company under analysis"]
    asset_type: Annotated[str, "Type of asset (e.g., 'stock', 'crypto')"]
    instrument_context: Annotated[str, "Resolved ticker identity and metadata"]
    trade_date: Annotated[str, "The target date for analysis (YYYY-MM-DD)"]

    sender: Annotated[str, "The identity of the agent that performed the last action"]

    # Research phase reports
    market_report: Annotated[str, "Technical analysis and market data report"]
    sentiment_report: Annotated[str, "Social media and news sentiment analysis report"]
    news_report: Annotated[str, "General news and macro-economic report"]
    fundamentals_report: Annotated[str, "Company financial health and fundamental metrics report"]

    # Investment Debate phase
    investment_debate_state: Annotated[InvestDebateState, "Encapsulated state for the Bull vs Bear debate"]
    investment_plan: Annotated[str, "Summary of the investment plan from the Research Manager"]

    # Trader transition
    trader_investment_plan: Annotated[str, "Refined execution plan from the Trader"]

    # Risk Management phase
    risk_debate_state: Annotated[RiskDebateState, "Encapsulated state for the Risk management discussion"]
    final_trade_decision: Annotated[str, "Final high-level decision (BUY/HOLD/SELL) and rationale"]
    past_context: Annotated[str, "Historical context and previous performance lessons"]
    # Pre-computed volatile data injected before graph.invoke (never in static system prompt)
    precomputed_indicators: Annotated[str, "Deterministic technical indicators from factor_engine"]
    epistemic_feedback: Annotated[str, "Prior analysis outcome — Bull/Bear audit requirement"]
