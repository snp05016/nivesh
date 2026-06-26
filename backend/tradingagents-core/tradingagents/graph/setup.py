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
_progress_stage: int = 0
_progress_total: int = 16
_progress_active = False
_progress_debate_round = 0

def get_progress_events() -> list[dict]:
    """Thread-safe read of accumulated progress events.
    
    Returns:
        list[dict]: A copy of the accumulated progress events.
    """
    with _progress_lock:
        return list(_progress_events)

def set_progress_total(t: int):
    """Set total stage count based on scan_type config.
    
    Args:
        t (int): The total number of stages.
    """
    global _progress_total
    with _progress_lock:
        _progress_total = t

def clear_progress_events():
    """Reset progress for a new analysis run."""
    global _progress_stage, _progress_active, _progress_debate_round
    with _progress_lock:
        _progress_events.clear()
        _progress_stage = 0
        _progress_active = True
        _progress_debate_round = 0

def _emit_progress(agent_name: str, status: str, message: str, llm_model: str, debate_round: int = 0):
    """Thread-safe append of a progress event with auto-incrementing stage.
    
    Args:
        agent_name (str): The name of the agent.
        status (str): The current status (e.g., 'thinking', 'complete', 'error').
        message (str): The progress message.
        llm_model (str): The name of the LLM model used.
        debate_round (int, optional): The current debate round. Defaults to 0.
    """
    global _progress_stage, _progress_debate_round
    with _progress_lock:
        if debate_round > 0:
            _progress_debate_round = debate_round
        if status == "thinking":
            _progress_stage += 1
        stage = _progress_stage
        total = _progress_total
    with _progress_lock:
        _progress_events.append({
            "agent": agent_name,
            "status": status,
            "message": message,
            "llm_model": llm_model,
            "stage": stage,
            "total_stages": total,
            "debate_round": debate_round,
            "timestamp": time.time(),
        })

def wrap_node_with_progress(agent_name: str, llm_model: str, inner_fn, debate_round: int = 0):
    """Wrap a graph node function to emit progress before and after execution.
    
    Stage numbers auto-increment via shared counter.
    
    Args:
        agent_name (str): The name of the agent.
        llm_model (str): The LLM model name.
        inner_fn (callable): The original node function to wrap.
        debate_round (int, optional): The current debate round. Defaults to 0.
        
    Returns:
        callable: The wrapped node function.
    """
    def wrapped(state):
        _emit_progress(agent_name, "thinking", f"Running {agent_name}...", llm_model, debate_round)
        try:
            result = inner_fn(state)
            _emit_progress(agent_name, "complete", f"{agent_name} completed", llm_model, debate_round)
            return result
        except Exception as e:
            _emit_progress(agent_name, "error", str(e)[:200], llm_model, debate_round)
            raise
    return wrapped

def _model_display(llm) -> str:
    """Map LLM config string to display name.
    
    Args:
        llm (Any): The LLM model object or string identifier.
        
    Returns:
        str: A human-readable display name for the model.
    """
    if llm is None:
        return "N/A"
    s = str(llm).lower()
    if "deepseek-v4-pro" in s or "v4-pro" in s:
        return "DeepSeek V4 Pro"
    if "reasoner" in s or "pro" in s:
        return "DeepSeek V4 Pro"
    if "deepseek" in s or "chat" in s:
        return "DeepSeek V4 Flash"
    if "haiku" in s:
        return "Claude Haiku 4.5"
    if "sonnet" in s or "claude-3" in s:
        return "Claude Sonnet"
    return "LLM"


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

        # Dynamic model display names from the actual LLM config
        quick_model = _model_display(self.quick_thinking_llm)
        deep_model = _model_display(self.deep_thinking_llm)
        analyst_labels = {"governance": "Governance Agent", "market": "Market Analyst", "social": "Sentiment Analyst",
                          "news": "News Analyst", "fundamentals": "Fundamentals Analyst"}

        analyst_factories = {}
        for key in ("governance", "market", "social", "news", "fundamentals"):
            factory = {
                "governance": lambda: create_governance_analyst(self.quick_thinking_llm),
                "market": lambda: create_market_analyst(self.quick_thinking_llm),
                "social": lambda: create_sentiment_analyst(self.quick_thinking_llm),
                "news": lambda: create_news_analyst(self.quick_thinking_llm),
                "fundamentals": lambda: create_fundamentals_analyst(self.quick_thinking_llm),
            }[key]
            label = analyst_labels[key]
            analyst_factories[key] = lambda f=factory, l=label, m=quick_model: wrap_node_with_progress(l, m, f())

        # Create researcher and manager nodes (with progress wrapping, dynamic models)
        bull_researcher_node = wrap_node_with_progress("Bull Researcher", quick_model,
            create_bull_researcher(self.quick_thinking_llm))
        bear_researcher_node = wrap_node_with_progress("Bear Researcher", quick_model,
            create_bear_researcher(self.quick_thinking_llm))
        research_manager_node = wrap_node_with_progress("Research Manager", deep_model,
            create_research_manager(self.deep_thinking_llm))
        trader_node = wrap_node_with_progress("Trader", quick_model,
            create_trader(self.quick_thinking_llm))

        aggressive_analyst = wrap_node_with_progress("Risk Committee (Aggressive)", quick_model,
            create_aggressive_debator(self.quick_thinking_llm))
        neutral_analyst = wrap_node_with_progress("Risk Committee (Neutral)", quick_model,
            create_neutral_debator(self.quick_thinking_llm))
        conservative_analyst = wrap_node_with_progress("Risk Committee (Conservative)", quick_model,
            create_conservative_debator(self.quick_thinking_llm))
        portfolio_manager_node = wrap_node_with_progress("Portfolio Manager", deep_model,
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

                if spec.key == "governance":
                    # Governance fast-track: clear → either next analyst or PM (skip pipeline on FAIL)
                    workflow.add_conditional_edges(
                        spec.clear_node,
                        self.conditional_logic.should_fast_track_governance,
                        {"Market Analyst": plan.specs[1].agent_node if len(plan.specs) > 1 else "Bull Researcher",
                         "Portfolio Manager": "Portfolio Manager"},
                    )
                elif i < len(plan.specs) - 1:
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
