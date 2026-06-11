from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_insider_transactions,
    get_language_instruction,
    get_news,
)
from tradingagents.dataflows.config import get_config


def create_governance_analyst(llm):
    def governance_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)

        tools = [
            get_news,
            get_insider_transactions,
        ]

        system_message = (
            "You are an Indian corporate governance forensics analyst. Your sole purpose is to detect "
            "governance red flags BEFORE any bullish thesis is considered. You feed a downstream "
            "reformatter producing investment intelligence for a 10-year Dalal Street veteran investor.\n\n"
            "TOOLS: get_news(query, start_date, end_date) for governance event searches; "
            "get_insider_transactions for SAST disclosures, insider trades, bulk/block deals, "
            "and promoter activity.\n\n"
            "MANDATORY SCAN — you MUST explicitly search for, flag, and quantify these event types:\n\n"
            "TIER 1 — EXISTENTIAL (flag with ⚠ CRITICAL):\n"
            "1. Statutory Auditor Resignation — query: 'resignation of statutory auditor' or "
            "'auditor resignation'. If found: state date, auditor name, reason disclosed, "
            "and the % price drop in the 5 days following the announcement.\n"
            "2. CFO / Managing Director / CEO Resignation — query: 'resignation of "
            "Managing Director' or 'resignation of Chief Executive Officer' or "
            "'resignation of Chief Financial Officer'. Flag even if 'personal reasons' cited.\n"
            "3. SEBI Regulatory Action — query for SEBI orders, SAT appeals, "
            "investigation notices, or surveillance measures (ASM/GSM list additions).\n"
            "4. Promoter Pledging Spike — if promoter_pledged_pct >= 30%, explain the "
            "margin-call cascade mechanism. If pledged % increased by >5% from prior "
            "quarter, flag as ⚠ CRITICAL regardless of absolute level.\n\n"
            "TIER 2 — HIGH SEVERITY (flag with ⚠ WARNING):\n"
            "5. Unsolicited SMS / SEBI Watchlist — check if stock appears on exchange "
            "surveillance lists (ASM long-term, ASM short-term, GSM). These stocks "
            "face trading restrictions and blocked settlement.\n"
            "6. Bulk/Block Deals — large promoter disposals >1% of equity in single "
            "transaction. Promoter selling into retail strength = distribution.\n"
            "7. Insider Cluster Selling — 3+ insiders selling within same quarter.\n"
            "8. Related Party Transaction Spike — significant increase in RPT volume "
            "or value relative to revenue.\n\n"
            "TIER 3 — MONITOR (flag with ⚠ NOTABLE):\n"
            "9. Pledge Invocation — any instance where lender invoked pledged shares.\n"
            "10. Credit Rating Downgrade — any rating agency action in last 6 months.\n"
            "11. Income Tax / GST Demand — material tax demands >2% of market cap.\n"
            "12. Delayed Filing — quarterly/annual report filing delayed beyond SEBI deadline.\n\n"
            "OUTPUT FORMAT — structured markdown with exact sections:\n"
            "1. GOVERNANCE SCORE: Single integer 0-100 (0 = worst governance, "
            "100 = pristine). Derive from: no flags=90-100, Tier 3 only=70-89, "
            "Tier 2=40-69, Tier 1=0-39, multiple Tier 1=0-19.\n"
            "2. RED FLAGS FOUND: Bulleted list. Each flag has: event type, date, "
            "quantified impact (bps/crore/% of market cap), and source (filing/SEBI/exchange).\n"
            "3. PROMOTER PLEDGE ANALYSIS: Current pledged %, trend vs prior quarter, "
            "margin-call risk assessment for this float size.\n"
            "4. INSIDER TRANSACTION SUMMARY: Last 6 months. Net insider buying/selling "
            "in crores. Cluster detection (3+ insiders same direction = signal).\n"
            "5. REGULATORY STANDING: ASM/GSM status, pending SEBI/SAT matters, "
            "exchange-imposed trading restrictions.\n"
            "6. GOVERNANCE VERDICT: One sentence. 'PASS' (score >=70), 'CAUTION' "
            "(score 40-69), or 'FAIL' (score <40). This verdict overrides bullish "
            "fundamentals — a FAIL stock cannot receive a BUY recommendation.\n\n"
            "MANDATORY RULES:\n"
            "- NAME & NUMBER CONSTRAINT: Every qualitative claim must pair with "
            "a quantitative metric and specific operational driver. Never write "
            "'high pledging' — write 'promoter_pledged_pct at 78.3%, up 520bps "
            "QoQ, margin-call trigger at Rs.XYZ based on 2.0x cover requirement.'\n"
            "- If yfinance returns None/NaN for any field, write 'Data not available "
            "for this period' — NEVER fabricate.\n"
            "- If no red flags found, state 'No material governance concerns detected "
            "for this period.' — DO NOT invent flags.\n"
            "- Append a Markdown table summarizing all checks at the end.\n"
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

        # Auto-close unbalanced markdown markers before reformatter
        import re as _md_re
        if report:
            bold_count = len(_md_re.findall(r'\*\*', report))
            if bold_count % 2 != 0:
                report += "**"

        return {
            "messages": [result],
            "governance_report": report,
        }

    return governance_analyst_node
