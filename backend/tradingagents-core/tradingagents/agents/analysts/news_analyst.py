from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_global_news,
    get_language_instruction,
    get_news,
)
from tradingagents.dataflows.config import get_config


def create_news_analyst(llm):
    def news_analyst_node(state):
        current_date = state["trade_date"]
        asset_type = state.get("asset_type", "stock")
        asset_label = "company" if asset_type == "stock" else "asset"
        instrument_context = get_instrument_context_from_state(state)

        tools = [
            get_news,
            get_global_news,
        ]

        system_message = (
            f"You are an Indian market news analyst. Your report feeds a downstream reformatter producing intelligence for a 10-year Dalal Street veteran investor.\n\n"
            f"TOOLS: get_news(query, start_date, end_date) for {asset_label}-specific news; get_global_news(curr_date, look_back_days, limit) for macro context.\n\n"
            "⚠ GOVERNANCE PRIORITY — scan explicitly and flag with '⚠ GOVERNANCE:' prefix if any found:\n"
            "1. Auditor resignation or audit qualification\n"
            "2. CFO or MD resignation\n"
            "3. SEBI show-cause notice, surveillance listing, or regulatory action\n"
            "Any governance event = mandatory key_risk regardless of other findings.\n\n"
            "MACRO TRANSLATION — never state vague observations:\n"
            "- Brent crude: quantify direct bps margin impact on this stock's specific sector.\n"
            "- US 10Y yield: translate as FPI liquidity flight trigger with estimated rupee outflow if available.\n"
            "- FII/DII block deals: treat as primary liquidity signal, weighted above narrative news.\n\n"
            "NAME & NUMBER: Every insight must carry a specific figure, date, or rupee/crore amount. No qualitative-only observations.\n\n"
            "Append a Markdown table of key findings at the end."
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
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
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

        return {
            "messages": [result],
            "news_report": report,
        }

    return news_analyst_node
