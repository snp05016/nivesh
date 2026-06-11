# TradingAgents/graph/setup.py

from typing import Any, Dict, List
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Send

from tradingagents.agents import *
from tradingagents.agents.utils.agent_states import AgentState

from .analyst_execution import build_analyst_execution_plan, AnalystNodeSpec
from .conditional_logic import ConditionalLogic


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

        analyst_factories = {
            "governance": lambda: create_governance_analyst(self.quick_thinking_llm),
            "market": lambda: create_market_analyst(self.quick_thinking_llm),
            "social": lambda: create_sentiment_analyst(self.quick_thinking_llm),
            "news": lambda: create_news_analyst(self.quick_thinking_llm),
            "fundamentals": lambda: create_fundamentals_analyst(self.quick_thinking_llm),
        }

        # Create researcher and manager nodes
        bull_researcher_node = create_bull_researcher(self.quick_thinking_llm)
        bear_researcher_node = create_bear_researcher(self.quick_thinking_llm)
        # Tier 2 (deep_thinking_llm) for trust-critical synthesis nodes
        research_manager_node = create_research_manager(self.deep_thinking_llm)
        trader_node = create_trader(self.quick_thinking_llm)

        # Create risk analysis nodes (Aggressive/Neutral/Conservative Debators — Tier 1)
        aggressive_analyst = create_aggressive_debator(self.quick_thinking_llm)
        neutral_analyst = create_neutral_debator(self.quick_thinking_llm)
        conservative_analyst = create_conservative_debator(self.quick_thinking_llm)
        # Tier 2 for Portfolio Manager final verdict
        portfolio_manager_node = create_portfolio_manager(self.deep_thinking_llm)

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
