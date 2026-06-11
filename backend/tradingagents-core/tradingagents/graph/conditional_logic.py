# TradingAgents/graph/conditional_logic.py

from tradingagents.agents.utils.agent_states import AgentState


class ConditionalLogic:
    """Handles conditional logic for determining graph flow."""

    def __init__(self, max_debate_rounds=1, max_risk_discuss_rounds=1):
        """Initialize with configuration parameters."""
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_discuss_rounds = max_risk_discuss_rounds

    def should_continue_market(self, state: AgentState):
        """Determine if market analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_market"
        return "Msg Clear Market"

    def should_continue_social(self, state: AgentState):
        """Determine if sentiment-analyst tool round should continue.

        Method name keeps the legacy ``social`` suffix to match the
        ``AnalystType.SOCIAL = "social"`` wire value (saved-config
        back-compat); the returned ``clear_node`` label uses the v0.2.5
        rename so it matches the node registered by the execution plan.
        """
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_social"
        return "Msg Clear Sentiment"

    def should_continue_news(self, state: AgentState):
        """Determine if news analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_news"
        return "Msg Clear News"

    def should_continue_fundamentals(self, state: AgentState):
        """Determine if fundamentals analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_fundamentals"
        return "Msg Clear Fundamentals"

    def should_continue_governance(self, state: AgentState):
        """Determine if governance analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_governance"
        return "Msg Clear Governance"

    def should_continue_debate(self, state: AgentState) -> str:
        """Determine if debate should continue with strict fallback routing."""
        # Safety fallback if state is missing
        debate_state = state.get("investment_debate_state")
        if not debate_state:
            return "Research Manager"  # Stop if state is corrupted

        count = debate_state.get("count", 0)

        # Hard safety limit to prevent infinite loops regardless of configuration
        SAFETY_CAP = 10
        effective_max = min(2 * self.max_debate_rounds, SAFETY_CAP)

        # Fix 2.14: Randomized deadlock-breaker — if debate loops past 3 rounds,
        # inject random resolution to avoid hitting SAFETY_CAP
        if count >= 3:
            import random as _rnd
            if _rnd.random() < 0.4:
                return "Research Manager"

        if count >= effective_max:
            return "Research Manager"
        
        current_response = debate_state.get("current_response", "")
        # Toggle between researchers based on the last speaker
        if "Bull" in current_response:
            return "Bear Researcher"
        return "Bull Researcher"

    def should_continue_risk_analysis(self, state: AgentState) -> str:
        """Determine if risk analysis should continue with strict fallback routing."""
        # Safety fallback if state is missing
        risk_state = state.get("risk_debate_state")
        if not risk_state:
            return "Portfolio Manager"  # Stop if state is corrupted

        count = risk_state.get("count", 0)
        
        # Hard safety limit to prevent infinite loops (3 agents * 3 rounds = 9)
        SAFETY_CAP = 15
        effective_max = min(3 * self.max_risk_discuss_rounds, SAFETY_CAP)

        if count >= effective_max:
            return "Portfolio Manager"
        
        latest_speaker = risk_state.get("latest_speaker", "")
        # Round-robin through risk analysts
        if "Aggressive" in latest_speaker:
            return "Conservative Analyst"
        if "Conservative" in latest_speaker:
            return "Neutral Analyst"
        return "Aggressive Analyst"
