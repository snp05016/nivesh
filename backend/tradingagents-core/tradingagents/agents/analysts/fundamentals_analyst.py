from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
    get_insider_transactions,
    get_language_instruction,
)
from tradingagents.dataflows.config import get_config


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)

        tools = [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
            get_insider_transactions,
        ]

        system_message = (
            "You are an Indian market fundamentals analyst. Your report feeds a downstream reformatter producing investment intelligence for a 10-year Dalal Street veteran investor.\n\n"
            "TOOLS: get_fundamentals for company overview, get_balance_sheet / get_cashflow / get_income_statement for financials, get_insider_transactions for promoter pledging and insider trades.\n\n"
            "MANDATORY RULES:\n"
            "1. NAME & NUMBER: Every qualitative claim requires a paired metric and operational driver. Never write 'strong margins' — always write 'EBITDA margins X.X% (+/-Ybps YoY), driven by [specific cost/revenue factor].'\n"
            "2. RISK-FIRST: Lead with (a) the primary structural vulnerability, (b) exact P&L impact if it materialises, (c) how the promoter behaved during a past stress event (2020 crash, 2022 rate shock).\n"
            "3. PROMOTER PLEDGE: Report promoter_pledged_pct explicitly. ≥30% = forced-liquidation risk — explain the margin-call cascade mechanism for this stock's float size.\n"
            "4. MANDATORY METRICS: ROCE, D/E ratio, FCF yield, working capital cycle days, OPM trend over last 4 quarters. Do not omit any.\n"
            "5. BANNED WORDS: 'strong', 'robust', 'headwinds', 'tailwinds', 'cautiously optimistic', 'value unlocking', 'navigating'. Replace with bps/crore/CAGR anchored statements.\n"
            "6. DATA PRESENT GUARD (Fix 2.17): If yfinance returns None/NaN for any financial field (EBITDA, OPM, revenue, etc.), write 'Data not available for this period' — NEVER fabricate, estimate, or hallucinate the value. Missing data is better than wrong data.\n"
            "7. M&A DETECTOR (Fix 2.43): If YoY revenue growth exceeds 100% or profit margins show abnormal swings (>2000bps), check for M&A activity, acquisitions, or divestments. Flag as 'CORPORATE_ACTION_ADJUSTMENT' and report organic (standalone) metrics separately from consolidated figures where available.\n\n"
            "Append a Markdown table of all key metrics at the end."
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

        # Fix 2.26: Auto-close unbalanced markdown markers before reformatter
        import re as _md_re
        if report:
            # Close unclosed ** bold markers
            bold_count = len(_md_re.findall(r'\*\*', report))
            if bold_count % 2 != 0:
                report += "**"
            # Close unclosed * italic markers (but not **)
            italic_stars = len(_md_re.findall(r'(?<!\*)\*(?!\*)', report))
            if italic_stars % 2 != 0:
                report += "*"
            # Close unclosed table rows (ensure trailing |)
            table_lines = [l for l in report.split('\n') if l.strip().startswith('|')]
            if table_lines:
                # Ensure consistent column count in each row
                col_counts = [len(l.split('|')) for l in table_lines]
                max_cols = max(col_counts) if col_counts else 0
                for i, l in enumerate(report.split('\n')):
                    if l.strip().startswith('|') and len(l.split('|')) < max_cols:
                        # Pad short rows with empty cells
                        padded = l + ' |' * (max_cols - len(l.split('|')))
                        report = report.replace(l, padded, 1)

        return {
            "messages": [result],
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
