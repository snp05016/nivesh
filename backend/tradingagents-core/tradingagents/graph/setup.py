# TradingAgents/graph/setup.py

import threading
import time
from typing import Any, Dict, List
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Send

from tradingagents.agents import *
from tradingagents.agents.utils.agent_states import AgentState

from .analyst_execution import build_analyst_execution_plan, AnalystNodeSpec
from .conditional_logic import ConditionalLogic

# Shared progress tracking for SSE streaming
_progress_lock = threading.Lock()
_progress_events: list[dict] = []

def get_progress_events() -> list[dict]:
    """Thread-safe read of accumulated progress events."""
    with _progress_lock:
        return list(_progress_events)

def clear_progress_events():
    """Reset progress for a new analysis run."""
    with _progress_lock:
        _progress_events.clear()

def _emit_progress(agent_name: str, status: str, message: str, llm_model: str, stage: int, total: int):
    """Thread-safe append of a progress event."""
    with _progress_lock:
        _progress_events.append({
            "agent": agent_name,
            "status": status,
            "message": message,
            "llm_model": llm_model,
            "stage": stage,
            "total_stages": total,
            "timestamp": time.time(),
        })

def wrap_node_with_progress(agent_name: str, llm_model: str, stage: int, total: int, inner_fn):
    """Wrap a graph node function to emit progress before and after execution."""
    def wrapped(state):
        _emit_progress(agent_name, "thinking", f"Running {agent_name}...", llm_model, stage, total)
        try:
            result = inner_fn(state)
            _emit_progress(agent_name, "complete", f"{agent_name} completed", llm_model, stage, total)
            return result
        except Exception as e:
            _emit_progress(agent_name, "error", str(e)[:200], llm_model, stage, total)
            raise
    return wrapped


# ---------------------------------------------------------------------------
# Fan-in merge node: collects parallel analyst results into AgentState
# ---------------------------------------------------------------------------

def _merge_analyst_results(state: AgentState) -> dict:
    """No-op merge node — parallel analyst writes directly into AgentState.

    LangGraph's parallel Send edges write each analyst's report field into
    the shared AgentState as individual updates. This node acts as the join
    point so the debate phase starts only after ALL analysts have finished.
    """
    return {}


class GraphSetup:
    """Handles the setup and configuration of the agent graph."""

    def __init__(
        self,
        quick_thinking_llm: Any,
        deep_thinking_llm: Any,
        tool_nodes: Dict[str, ToolNode],
        conditional_logic: ConditionalLogic,
        analyst_concurrency_limit: int = 1,
    ):
        """Initialize with required components."""
        self.quick_thinking_llm = quick_thinking_llm
        self.deep_thinking_llm = deep_thinking_llm
        self.tool_nodes = tool_nodes
        self.conditional_logic = conditional_logic
        self.analyst_concurrency_limit = analyst_concurrency_limit

    def setup_graph(
        self, selected_analysts=["governance", "market", "social", "news", "fundamentals"]
    ):
        """Set up and compile the agent workflow graph.

        When ``analyst_concurrency_limit > 1`` the analyst committee runs in
        parallel via LangGraph ``Send`` fan-out edges. All analysts fire
        concurrently from START, and a lightweight merge node acts as the
        fan-in join point before the Bull/Bear debate begins.

        When ``analyst_concurrency_limit == 1`` (default) analysts run
        sequentially to avoid rate-limit bursts on paid APIs.

        Args:
            selected_analysts (list): List of analyst types to include. Options:
                - "market": Market analyst (price trends)
                - "social": Sentiment analyst (news + social signals)
                - "news": News analyst (macro & red-flag tracking)
                - "fundamentals": Fundamentals analyst (balance sheets)
        """
        plan = build_analyst_execution_plan(
            selected_analysts,
            concurrency_limit=self.analyst_concurrency_limit,
        )

        # Analyst stage numbers (after Factor Engine=0, Epistemic=1)
        TOTAL_STAGES = 20
        _analyst_stages = {"governance": 2, "market": 3, "social": 4, "news": 5, "fundamentals": 6}
        _analyst_labels = {"governance": "Governance Agent", "market": "Market Analyst", "social": "Sentiment Analyst", "news": "News Analyst", "fundamentals": "Fundamentals Analyst"}

        analyst_factories = {}
        for key in ("governance", "market", "social", "news", "fundamentals"):
            factory = {
                "governance": lambda: create_governance_analyst(self.quick_thinking_llm),
                "market": lambda: create_market_analyst(self.quick_thinking_llm),
                "social": lambda: create_sentiment_analyst(self.quick_thinking_llm),
                "news": lambda: create_news_analyst(self.quick_thinking_llm),
                "fundamentals": lambda: create_fundamentals_analyst(self.quick_thinking_llm),
            }[key]
            stage = _analyst_stages[key]
            label = _analyst_labels[key]
            analyst_factories[key] = lambda f=factory, s=stage, l=label: wrap_node_with_progress(l, "DeepSeek V4 Flash", s, TOTAL_STAGES, f())

        # Create researcher and manager nodes (with progress wrapping)
        bull_researcher_node = wrap_node_with_progress(
            "Bull Researcher", "DeepSeek V4 Flash", 7, TOTAL_STAGES,
            create_bull_researcher(self.quick_thinking_llm))
        bear_researcher_node = wrap_node_with_progress(
            "Bear Researcher", "DeepSeek V4 Flash", 8, TOTAL_STAGES,
            create_bear_researcher(self.quick_thinking_llm))
        # Tier 2 (deep_thinking_llm) for trust-critical synthesis nodes
        research_manager_node = wrap_node_with_progress(
            "Research Manager", "Claude Haiku 4.5", 10, TOTAL_STAGES,
            create_research_manager(self.deep_thinking_llm))
        trader_node = wrap_node_with_progress(
            "Trader", "DeepSeek V4 Flash", 11, TOTAL_STAGES,
            create_trader(self.quick_thinking_llm))

        # Create risk analysis nodes (Aggressive/Neutral/Conservative Debators — Tier 1)
        aggressive_analyst = wrap_node_with_progress(
            "Risk Committee", "DeepSeek V4 Flash", 12, TOTAL_STAGES,
            create_aggressive_debator(self.quick_thinking_llm))
        neutral_analyst = wrap_node_with_progress(
            "Risk Committee", "DeepSeek V4 Flash", 13, TOTAL_STAGES,
            create_neutral_debator(self.quick_thinking_llm))
        conservative_analyst = wrap_node_with_progress(
            "Risk Committee", "DeepSeek V4 Flash", 14, TOTAL_STAGES,
            create_conservative_debator(self.quick_thinking_llm))
        # Tier 2 for Portfolio Manager final verdict
        portfolio_manager_node = wrap_node_with_progress(
            "Portfolio Manager", "Claude Haiku 4.5", 15, TOTAL_STAGES,
            create_portfolio_manager(self.deep_thinking_llm))

        # Create workflow
        workflow = StateGraph(AgentState)

        # ── Register analyst nodes ──────────────────────────────────────────
        for spec in plan.specs:
            workflow.add_node(spec.agent_node, analyst_factories[spec.key]())
            workflow.add_node(spec.clear_node, create_msg_delete())
            workflow.add_node(spec.tool_node, self.tool_nodes[spec.key])

        # ── Register downstream nodes ──────────────────────────────────────
        workflow.add_node("Bull Researcher", bull_researcher_node)
        workflow.add_node("Bear Researcher", bear_researcher_node)
        workflow.add_node("Research Manager", research_manager_node)
        workflow.add_node("Trader", trader_node)
        workflow.add_node("Aggressive Analyst", aggressive_analyst)
        workflow.add_node("Neutral Analyst", neutral_analyst)
        workflow.add_node("Conservative Analyst", conservative_analyst)
        workflow.add_node("Portfolio Manager", portfolio_manager_node)

        # ── Wire analyst edges ─────────────────────────────────────────────
        if self.analyst_concurrency_limit > 1 and len(plan.specs) > 1:
            # PARALLEL PATH: fan-out via Send, fan-in at "Analysts Done"
            workflow.add_node("Analysts Done", _merge_analyst_results)

            def _fan_out_analysts(state: AgentState) -> List[Send]:
                """Dispatch all analyst nodes simultaneously."""
                return [Send(spec.agent_node, state) for spec in plan.specs]

            workflow.add_conditional_edges(START, _fan_out_analysts)

            for spec in plan.specs:
                # Each analyst loops with its tools until complete, then clears
                # messages and fans-in to the merge node.
                workflow.add_conditional_edges(
                    spec.agent_node,
                    getattr(self.conditional_logic, f"should_continue_{spec.key}"),
                    [spec.tool_node, spec.clear_node],
                )
                workflow.add_edge(spec.tool_node, spec.agent_node)
                workflow.add_edge(spec.clear_node, "Analysts Done")

            workflow.add_edge("Analysts Done", "Bull Researcher")

        else:
            # SEQUENTIAL PATH: original chain (default, rate-limit friendly)
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

        # ── Adversarial Researcher Debate (Bull vs Bear, 1 round) ──────────
        workflow.add_conditional_edges(
            "Bull Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bear Researcher": "Bear Researcher",
                "Research Manager": "Research Manager",
            },
        )
        workflow.add_conditional_edges(
            "Bear Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bull Researcher": "Bull Researcher",
                "Research Manager": "Research Manager",
            },
        )

        # ── Research Manager → Trader ──────────────────────────────────────
        workflow.add_edge("Research Manager", "Trader")

        # ── Risk Review Committee (Aggressive / Neutral / Conservative) ────
        workflow.add_edge("Trader", "Aggressive Analyst")
        workflow.add_conditional_edges(
            "Aggressive Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Conservative Analyst": "Conservative Analyst",
                "Portfolio Manager": "Portfolio Manager",
            },
        )
        workflow.add_conditional_edges(
            "Conservative Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Neutral Analyst": "Neutral Analyst",
                "Portfolio Manager": "Portfolio Manager",
            },
        )
        workflow.add_conditional_edges(
            "Neutral Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Aggressive Analyst": "Aggressive Analyst",
                "Portfolio Manager": "Portfolio Manager",
            },
        )

        # ── Portfolio Manager Final Decision → END ─────────────────────────
        workflow.add_edge("Portfolio Manager", END)

        return workflow
