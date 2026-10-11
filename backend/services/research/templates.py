"""Fixed server texts (spec 6.4) and the template narrative ``tf-1`` (spec 7.7).

Every string here is shown verbatim to users and must stay byte-identical to
spec 6.4 and the contract fixtures (``docs/research/contract/fixtures``).
Outlook, disclaimer, model-card and range texts are never produced by an LLM.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

TEMPLATE_VERSION = "tf-1"

# Tier texts (tx-2), keyed by HorizonOutlook.evidence_tier.
TIER_TEXT: dict[str, str] = {
    "validated_edge": (
        "This method met all of its pre-set statistical checks at this horizon. "
        "It is not a forecast for this stock."
    ),
    "weak_evidence": (
        "Testing found some evidence at this horizon, but not enough to show a stock-level estimate."
    ),
    "no_reliable_edge": (
        "No reliable edge at this horizon: in testing, the model did not rank stocks better than "
        "simple rules with enough confidence, so no stock-level estimate is shown. "
        "This says nothing good or bad about this stock."
    ),
    "out_of_universe": (
        "Outlooks are computed only for the 200 most-traded NSE stocks. "
        "The figures below are descriptive."
    ),
    "unavailable": "The outlook is unavailable for this report.",
}

DISCLAIMER_ID = "research_v1"
DISCLAIMER_TEXT = (
    "Nivesh is not registered with SEBI as a research analyst or investment adviser. This stock "
    "report is general, educational information computed from public market data. It is not "
    "investment advice, a research report or a recommendation to buy, sell or hold any security, "
    "and it does not consider your finances or goals. Figures describe the past; statistical "
    "patterns can weaken or vanish. Investments in the securities market are subject to market "
    "risks. Read all related documents carefully before investing."
)

AI_DISCLOSURE = (
    "An AI language model (DeepSeek) turns the computed figures into sentences. It does not "
    "compute or choose any number; an automated checker verifies every sentence, and a fixed "
    "template is shown if the check fails. Only public market data is sent to the AI provider."
)

LEGACY_GONE_TEXT = "Stock reports have moved. Update Nivesh to see the new stock report."

# v1 has no registered-entity disclaimer, so any RESEARCH_SEBI_RA_REG_NO is invalid
# config until legal supplies this text (spec 6.4, 9.3).
RA_DISCLAIMER_TEXT: str | None = None

# Band phrases (spec 7.2): (exclusive upper bound of the percentile, phrase).
BAND_PHRASES: tuple[tuple[float, str], ...] = (
    (20.0, "among the lowest fifth of {ref}"),
    (40.0, "below the middle of {ref}"),
    (60.0, "around the middle of {ref}"),
    (80.0, "above the middle of {ref}"),
    (math.inf, "among the highest fifth of {ref}"),
)

# Spec 4.8 fixed family order.
FACTOR_FAMILIES: tuple[str, ...] = ("momentum", "reversal", "risk", "liquidity", "trend")
_FAMILY_LABEL_SUFFIX = " compared with the 200 most-traded NSE stocks"
_CLAUSES_PER_SENTENCE = 3


def band_phrase(p: float, ref: str) -> str:
    """Phrase for percentile ``p`` (0-100) against reference group ``ref``."""
    return next(phrase for upper, phrase in BAND_PHRASES if p < upper).format(ref=ref)


def _ph(placeholder_id: str) -> str:
    return "{{" + placeholder_id + "}}"


def template_narrative(payload: Mapping[str, Any]) -> dict[str, Any]:
    """The ``tf-1`` narrative for a facts payload, with placeholders unrendered.

    Returns the same shape the LLM must produce,
    ``{"summary": str, "sections": {"risk", "factor_profile", "fundamentals"}}``,
    so it goes through ``validator.validate`` and ``validator.render`` like LLM
    output. Sentences are ``"{label}: {{id}}."`` for ok facts only (labels are
    masked by the validator). Paired or grouped facts share a sentence so each
    field stays within the 3-sentence limit.
    """
    facts: dict[str, Mapping[str, Any]] = {f["id"]: f for f in payload.get("facts", [])}
    bands: Mapping[str, str] = payload.get("bands", {})

    def line(fid: str) -> list[str]:
        return [f"{facts[fid]['label']}: {_ph(fid)}."] if fid in facts else []

    def band_line(fid: str) -> list[str]:
        if fid not in facts or f"{fid}.band" not in bands:
            return []
        return [f"{facts[fid]['label']}: {_ph(fid + '.band')}."]

    name = payload["company_name"]
    summary = (
        [f"{name} last closed at {_ph('snapshot.last_close')} on {_ph('as_of')}."]
        if "snapshot.last_close" in facts
        else [f"{name}: figures as of {_ph('as_of')}."]
    )
    summary += line("snapshot.r_12m_pct") + band_line("risk.vol_pctl")

    risk = line("risk.vol_ewma_ann_pct") + line("risk.drawdown.max_3y_pct")
    low, high = "risk.range.21.low_pct", "risk.range.21.high_pct"
    if low in facts and high in facts:
        high_label = facts[high]["label"]
        risk.append(
            f"{facts[low]['label']}: {_ph(low)}; {high_label[:1].lower()}{high_label[1:]}: {_ph(high)}."
        )
    else:
        risk += line(low) + line(high)
    if not risk:
        # The validator requires the risk field to use a risk fact whenever one exists.
        first = next((fid for fid in facts if fid.startswith("risk.")), None)
        risk = line(first) if first else []

    clauses: list[str] = []
    for family in FACTOR_FAMILIES:
        fid = f"factor.{family}.pctl"
        if fid in facts and f"{fid}.band" in bands:
            label = str(facts[fid]["label"])
            family_name = label.removesuffix(_FAMILY_LABEL_SUFFIX)
            clauses.append(f"{family_name} was {_ph(fid + '.band')}")
    factor_profile = [
        _join_clauses(clauses[i : i + _CLAUSES_PER_SENTENCE])
        for i in range(0, len(clauses), _CLAUSES_PER_SENTENCE)
    ]

    fundamentals = line("fund.pe_ttm") + line("fund.roe_pct")
    if "fund.piotroski.f_score" in facts and "fund.piotroski.max_possible" in facts:
        fundamentals.append(
            f"Piotroski F-score: {_ph('fund.piotroski.f_score')} of "
            f"{_ph('fund.piotroski.max_possible')} available checks."
        )

    return {
        "summary": " ".join(summary),
        "sections": {
            "risk": " ".join(risk),
            "factor_profile": " ".join(factor_profile),
            "fundamentals": " ".join(fundamentals),
        },
    }


def _join_clauses(clauses: list[str]) -> str:
    """'A was x', 'B was y', 'C was z' -> 'A was x, b was y and c was z.'"""
    parts = [clauses[0]] + [c[:1].lower() + c[1:] for c in clauses[1:]]
    if len(parts) == 1:
        return parts[0] + "."
    return ", ".join(parts[:-1]) + " and " + parts[-1] + "."
