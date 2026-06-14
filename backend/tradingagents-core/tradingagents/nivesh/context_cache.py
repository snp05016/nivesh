"""
nivesh.context_cache — Prefix-Aligned Context Stratification (Task 13.3)
=========================================================================
Implements a two-tier prompt structure that maximises Anthropic prompt-cache
hit ratios by separating static persona definitions from volatile per-ticker
data:

    Tier A — Static Persona Cache (SystemMessage / Breakpoint 1)
        • Institutional analyst personas, tool definitions, output rules.
        • Never changes between runs. Cached at the system-prompt boundary.
        • Built once via ``build_static_persona_block()``.

    Tier B — Ticker History Context (HumanMessage / Breakpoint 2)
        • Dynamic: prior analysis summaries for the current ticker.
        • Serialised deterministically so the cache key is stable across
          calls with the same ticker history.
        • Built via ``build_ticker_history_block()``.

Both blocks are returned as Anthropic content-array dicts with
``cache_control: {"type": "ephemeral"}`` ready to pass directly to
``client.messages.create(system=...)``.

Usage
-----
    from tradingagents.nivesh.context_cache import (
        build_static_persona_block,
        build_ticker_history_block,
        build_system_array,
    )

    system_array = build_system_array(
        ticker="SUZLON.NS",
        prior_analyses=prior_analyses_list,
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        system=system_array,
        messages=[{"role": "user", "content": user_msg}],
        ...
    )
"""

from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------------------
# Tier A — Static Persona Block
# Cached at Breakpoint 1: sent once, then re-used from cache on every
# subsequent call that shares this exact text prefix.
# ---------------------------------------------------------------------------

_STATIC_PERSONA = """\
INSTITUTIONAL ANALYST PERSONAS
================================
You are a panel of specialised Indian equity research professionals operating
as a single integrated intelligence. Each sub-persona contributes in turn:

1. MARKET ANALYST (Price & Technicals)
   Role: Evaluate price structure, momentum, volume profiles, and DMA signals.
   Deliverable: Behavioural translation of every technical indicator — no raw
   numbers without human-readable interpretation (see BEHAVIORAL TRANSLATION rules).

2. NEWS ANALYST (Red Flags & Macro Catalysts)
   Role: Filter signal from noise in recent corporate announcements, SEBI
   filings, and macro headlines. Flag governance red flags before discussing
   upside.

3. FUNDAMENTALS ANALYST (Balance Sheet & Cash Flow)
   Role: Decompose P&L quality, working-capital efficiency, FCF generation,
   and debt-service capacity using Indian GAAP / Ind-AS framing.

4. BULL RESEARCHER
   Role: Build the strongest possible long case. Ground every claim in a
   measurable metric. Challenge the bear thesis with specific counter-evidence.

5. BEAR RESEARCHER
   Role: Build the strongest possible short/avoid case. Identify governance
   landmines, valuation traps, and sector headwinds with quantified impact.

6. RESEARCH MANAGER (Synthesis Judge)
   Role: Weigh the debate. Assign a directional verdict with a confidence
   band. Do not hedge — commit to the side with stronger evidence.

7. TRADER
   Role: Translate the research verdict into an unhedged trade recommendation
   (Buy / Hold / Sell) with explicit entry, target, and stop levels in ₹.

8. RISK COMMITTEE (Aggressive / Neutral / Conservative Analysts)
   Role: Stress-test the trader's levels from three risk-tolerance profiles.
   Output a blended risk-adjusted position-size recommendation.

9. PORTFOLIO MANAGER (Final Verdict)
   Role: Synthesise all prior nodes into a single, definitive investment
   decision with full rationale grounded in specific evidence.

TOOL DEFINITIONS
=================
The following data tools are available to analyst nodes. Use them to ground
assertions in live data rather than training-set priors:

- get_stock_data(ticker)        → OHLCV price history (1Y, daily)
- get_indicators(ticker)        → RSI, MACD, Bollinger, SMA 50/200
- get_fundamentals(ticker)      → PE, PB, EPS, ROE, ROCE, D/E
- get_balance_sheet(ticker)     → Assets, liabilities, equity (Ind-AS)
- get_cashflow(ticker)          → Operating, investing, financing CF
- get_income_statement(ticker)  → Revenue, EBITDA, PAT (trailing 8Q)
- get_news(ticker)              → Recent news headlines + snippets
- get_insider_transactions(ticker) → SAST disclosures, bulk deals
- get_global_news(query)        → Macro headlines (Fed, crude, FII flows)

BEHAVIORAL TRANSLATION RULES (mandatory for all technical signals)
===================================================================
- RSI > 70  → "Retail momentum overextended; institutional profit-booking zone."
- RSI < 30  → "Retail capitulation; potential institutional accumulation zone."
- 200 SMA   → "Average historical cost-basis of long-term institutional participants."
- MACD bearish crossover → "Loss of institutional conviction; short-term momentum
  breaking below medium-term trend."
- Volume rising / price falling → "Smart money distribution under retail cover."
- Volume falling / price rising → "Rally structurally hollow; retail trapped at
  distribution prices."

INDIAN MARKET PRIORITY WEIGHTING (enforce this exact ordering in every output)
=================================================================================
1. Management Quality — governance, capital allocation, promoter pledging
2. Institutional Flow — FII/DII/promoter stake changes, bulk deals, block trades
3. Contrarian Sentiment — operator patterns, retail herd behaviour, social buzz
   (HIGH retail excitement = contrarian risk, NOT bullish signal)
4. Core Fundamentals — revenue CAGR, margin trajectory, ROE/ROCE, FCF yield
5. Policy Tailwinds — PLI schemes, government capex, sector-specific regulation
6. Global Macro — Fed policy, crude oil, DXY, EM risk sentiment
"""


def build_static_persona_block() -> dict[str, Any]:
    """Return the static persona system block with ephemeral cache control.

    This block is placed first in the system array so it anchors Breakpoint 1.
    Once cached by Anthropic, subsequent calls skip tokenising this entire
    block and the input-token cost falls to the cache-read rate.
    """
    return {
        "type": "text",
        "text": _STATIC_PERSONA,
        "cache_control": {"type": "ephemeral"},
    }


# ---------------------------------------------------------------------------
# Tier B — Ticker History Context Block
# Cached at Breakpoint 2: deterministically serialised so the cache key is
# stable whenever the same N prior analyses are passed.
# ---------------------------------------------------------------------------

def build_ticker_history_block(
    ticker: str,
    prior_analyses: list[dict],
) -> dict[str, Any] | None:
    """Serialise ticker history into an ephemeral-cached system block.

    Returns ``None`` when there are no prior analyses so the caller can
    simply skip appending an empty block.

    The last 15 analyses are used (oldest-first) with keys sorted for a
    stable JSON serialisation — this keeps the cache key identical across
    calls with the same set of analyses even if dict ordering differs.
    """
    if not prior_analyses:
        return None

    history_points = []
    for p in prior_analyses[-15:]:
        history_points.append(
            {
                "date": p.get("analysis_date"),
                "signal": p.get("signal"),
                "conf": p.get("confidence_pct"),
                "target_3m": (p.get("target_prices") or {}).get("short_term_3m"),
            }
        )
    serialized = json.dumps(history_points, sort_keys=True)

    return {
        "type": "text",
        "text": f"PREVIOUS HISTORICAL ANALYSES FOR {ticker} (CONTEXT ONLY):\n{serialized}",
        "cache_control": {"type": "ephemeral"},
    }


# ---------------------------------------------------------------------------
# Convenience: build the full system array in one call
# ---------------------------------------------------------------------------

def build_system_array(
    ticker: str = "",
    prior_analyses: list[dict] | None = None,
) -> list[dict[str, Any]]:
    """Assemble the full prefix-aligned system array for a reformatter call.

    The array always starts with the static persona block (Breakpoint 1).
    When ``prior_analyses`` is non-empty, the ticker history block
    (Breakpoint 2) is appended immediately after.

    Parameters
    ----------
    ticker:
        Ticker symbol used as a label in the history block, e.g. ``"SUZLON.NS"``.
    prior_analyses:
        List of previous analysis dicts for this ticker (may be empty or None).

    Returns
    -------
    list[dict]
        Ready to pass as ``system=`` to ``anthropic.client.messages.create()``.
    """
    system_array: list[dict[str, Any]] = [build_static_persona_block()]

    history_block = build_ticker_history_block(ticker, prior_analyses or [])
    if history_block is not None:
        system_array.append(history_block)

    return system_array
