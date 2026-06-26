from dataclasses import dataclass
from time import monotonic
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class AnalystNodeSpec:
    """Specification for an analyst node in the graph.
    
    Attributes:
        key (str): The unique identifier for the analyst.
        agent_node (str): The node name for the agent in the graph.
        clear_node (str): The node name for clearing messages.
        tool_node (str): The node name for the tools used by the analyst.
        report_key (str): The key under which the analyst's report is saved in the state.
    """
    key: str
    agent_node: str
    clear_node: str
    tool_node: str
    report_key: str


@dataclass(frozen=True)
class AnalystExecutionPlan:
    """Represents a plan for executing analyst nodes.
    
    Attributes:
        specs (List[AnalystNodeSpec]): A list of analyst node specifications.
        concurrency_limit (int): The maximum number of analysts to run concurrently.
    """
    specs: List[AnalystNodeSpec]
    concurrency_limit: int


ANALYST_NODE_SPECS: Dict[str, AnalystNodeSpec] = {
    "governance": AnalystNodeSpec(
        key="governance",
        agent_node="Governance Analyst",
        clear_node="Msg Clear Governance",
        tool_node="tools_governance",
        report_key="governance_report",
    ),
    "market": AnalystNodeSpec(
        key="market",
        agent_node="Market Analyst",
        clear_node="Msg Clear Market",
        tool_node="tools_market",
        report_key="market_report",
    ),
    "social": AnalystNodeSpec(
        # Wire key stays "social" for saved-config back-compat; the
        # user-facing label is "Sentiment Analyst" to match the rename
        # that landed in v0.2.5 (sentiment_analyst now ingests news +
        # StockTwits + Reddit, not just social media).
        key="social",
        agent_node="Sentiment Analyst",
        clear_node="Msg Clear Sentiment",
        tool_node="tools_social",
        report_key="sentiment_report",
    ),
    "news": AnalystNodeSpec(
        key="news",
        agent_node="News Analyst",
        clear_node="Msg Clear News",
        tool_node="tools_news",
        report_key="news_report",
    ),
    "fundamentals": AnalystNodeSpec(
        key="fundamentals",
        agent_node="Fundamentals Analyst",
        clear_node="Msg Clear Fundamentals",
        tool_node="tools_fundamentals",
        report_key="fundamentals_report",
    ),
}


def build_analyst_execution_plan(
    selected_analysts: Iterable[str],
    concurrency_limit: int = 1,
) -> AnalystExecutionPlan:
    """Build an execution plan for the selected analysts.
    
    Args:
        selected_analysts (Iterable[str]): An iterable of analyst keys to include.
        concurrency_limit (int, optional): Maximum number of concurrent analysts. Defaults to 1.
        
    Returns:
        AnalystExecutionPlan: The built execution plan.
        
    Raises:
        ValueError: If concurrency_limit is less than 1, if an unknown analyst key is provided, or if no analysts are selected.
    """
    if concurrency_limit < 1:
        raise ValueError("analyst concurrency limit must be >= 1")

    specs: List[AnalystNodeSpec] = []
    for analyst_key in selected_analysts:
        spec = ANALYST_NODE_SPECS.get(analyst_key)
        if spec is None:
            raise ValueError(f"unknown analyst key: {analyst_key}")
        specs.append(spec)

    if not specs:
        raise ValueError("at least one analyst must be selected")

    return AnalystExecutionPlan(specs=specs, concurrency_limit=concurrency_limit)


def get_initial_analyst_node(plan: AnalystExecutionPlan) -> str:
    """Get the node name of the first analyst in the execution plan.
    
    Args:
        plan (AnalystExecutionPlan): The execution plan.
        
    Returns:
        str: The name of the initial agent node.
    """
    return plan.specs[0].agent_node


class AnalystWallTimeTracker:
    """Tracks the wall-clock execution time of each analyst node."""
    
    def __init__(self, plan: AnalystExecutionPlan):
        """Initialize the wall time tracker with an execution plan.
        
        Args:
            plan (AnalystExecutionPlan): The analyst execution plan to track.
        """
        self.plan = plan
        self._started_at: Dict[str, float] = {}
        self._wall_times: Dict[str, float] = {}

    def mark_started(self, analyst_key: str, started_at: Optional[float] = None) -> None:
        if analyst_key not in ANALYST_NODE_SPECS:
            raise ValueError(f"unknown analyst key: {analyst_key}")
        self._started_at.setdefault(analyst_key, monotonic() if started_at is None else started_at)

    def mark_completed(
        self,
        analyst_key: str,
        completed_at: Optional[float] = None,
    ) -> None:
        if analyst_key not in ANALYST_NODE_SPECS:
            raise ValueError(f"unknown analyst key: {analyst_key}")
        if analyst_key in self._wall_times:
            return
        started_at = self._started_at.get(analyst_key)
        if started_at is None:
            return
        finished_at = monotonic() if completed_at is None else completed_at
        self._wall_times[analyst_key] = max(0.0, finished_at - started_at)

    def get_wall_times(self) -> Dict[str, float]:
        return dict(self._wall_times)

    def format_summary(self) -> str:
        parts = []
        for spec in self.plan.specs:
            duration = self._wall_times.get(spec.key)
            if duration is not None:
                label = spec.agent_node.removesuffix(" Analyst")
                parts.append(f"{label} {duration:.2f}s")
        if not parts:
            return "Analyst wall time: pending"
        return "Analyst wall time: " + " | ".join(parts)


def sync_analyst_tracker_from_chunk(
    tracker: AnalystWallTimeTracker,
    chunk: Dict[str, str],
    now: Optional[float] = None,
) -> None:
    """Synchronize the analyst time tracker based on graph chunks.
    
    Updates the start and completion times of analysts based on the presence
    of their reports in the chunk data.
    
    Args:
        tracker (AnalystWallTimeTracker): The tracker to synchronize.
        chunk (Dict[str, str]): The current chunk of state data.
        now (Optional[float], optional): The current time. Defaults to monotonic time.
    """
    current_time = monotonic() if now is None else now
    active_found = False

    for spec in tracker.plan.specs:
        has_report = bool(chunk.get(spec.report_key))

        if has_report:
            tracker.mark_started(spec.key, started_at=current_time)
            tracker.mark_completed(spec.key, completed_at=current_time)
            continue

        if not active_found:
            tracker.mark_started(spec.key, started_at=current_time)
            active_found = True
