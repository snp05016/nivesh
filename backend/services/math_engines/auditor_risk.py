import logging
"""
Auditor Risk Quantification — deterministic risk scoring matrix (Task 30).

Evaluates governance risk based on:
- Big-4 auditor presence (Deloitte, PwC, EY, KPMG)
- Auditor changes (resignations are red flags)
- Regulatory actions (SEBI penalties, NCLT proceedings)
- Auditor tenure (excessive tenure can signal complacency)
"""
import os
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class AuditorRiskScoreResponse(BaseModel):
    risk_score: int
    risk_level: str
    is_big4_auditor: bool
    factors: List[str]
    explanation: str

BIG4_AUDITORS = {
    "Deloitte", "Deloitte Haskins & Sells", "Deloitte Touche Tohmatsu",
    "PwC", "Price Waterhouse", "Price Waterhouse & Co",
    "Price Waterhouse Chartered Accountants", "PricewaterhouseCoopers",
    "EY", "Ernst & Young", "Ernst and Young",
    "SR Batliboi", "SRBC & Co", "S.R. Batliboi & Co",
    "KPMG", "KPMG India", "BSR & Co", "BSR & Associates",
    "B S R & Co", "B S R and Associates",
}

REGULATORY_ACTION_KEYWORDS = [
    "SEBI penalty", "SEBI order", "SEBI action", "SEBI investigation",
    "NCLT", "NCLAT", "SFIO", "MCA penalty", "MCA investigation",
    "RBI penalty", "IRDA penalty", "CAG audit objection",
    "fraud", "misstatement", "qualification", "adverse opinion",
    "disclaimer of opinion", "emphasis of matter", "key audit matter escalation",
]


def _fuzzy_big4(auditor_name: str) -> bool:
    """Check if auditor name matches any Big-4 variant."""
    name_upper = auditor_name.upper().replace(" LLP", "").replace(" LLP", "")
    for big4 in BIG4_AUDITORS:
        if big4.upper().replace(" LLP", "") in name_upper:
            return True
    return False


def compute_auditor_risk_score(
    current_auditor: str,
    previous_auditor: Optional[str] = None,
    regulatory_actions: Optional[list[str]] = None,
    years_with_current: int = 0,
    has_qualified_opinion: bool = False,
    promoter_pledging_pct: float = 0.0,
) -> AuditorRiskScoreResponse:
    """
    Deterministic auditor risk matrix (0-100 scale).

    Parameters
    ----------
    current_auditor : str
        Name of current statutory auditor.
    previous_auditor : str, optional
        Previous auditor (if changed recently).
    regulatory_actions : list[str], optional
        Regulatory actions against the company (SEBI, NCLT, etc.).
    years_with_current : int, default 0
        Number of years with current auditor.
    has_qualified_opinion : bool, default False
        Whether most recent audit report has a qualified opinion.
    promoter_pledging_pct : float, default 0.0
        Percentage of promoter holding pledged (0-100).

    Returns
    -------
    dict with risk_score (0-100), risk_level, and detailed explanation.
    """
    risk_score = 0
    factors = []

    # Factor 1: Big-4 presence
    is_big4 = _fuzzy_big4(current_auditor)
    if not is_big4:
        risk_score += 15
        factors.append("Non-Big-4 auditor (+15)")
    else:
        factors.append("Big-4 auditor (baseline)")

    # Factor 2: Auditor change
    if previous_auditor:
        was_big4 = _fuzzy_big4(previous_auditor) if previous_auditor else False
        if previous_auditor != current_auditor:
            if was_big4 and not is_big4:
                risk_score += 30
                factors.append("Auditor downgrade: Big-4 to non-Big-4 (+30)")
            elif not was_big4 and is_big4:
                risk_score -= 10
                factors.append("Auditor upgrade: non-Big-4 to Big-4 (-10)")
            else:
                risk_score += 20
                factors.append("Auditor change (+20)")

    # Factor 3: Regulatory actions
    if regulatory_actions:
        action_count = len([a for a in regulatory_actions
                           if any(kw.lower() in a.lower() for kw in REGULATORY_ACTION_KEYWORDS)])
        if action_count > 0:
            action_penalty = min(50, action_count * 25)
            risk_score += action_penalty
            factors.append(f"Regulatory actions: {action_count} detected (+{action_penalty})")

    # Factor 4: Qualified opinion
    if has_qualified_opinion:
        risk_score += 25
        factors.append("Qualified/adverse audit opinion (+25)")

    # Factor 5: Excessive tenure
    if years_with_current > 10:
        risk_score += 10
        factors.append(f"Long auditor tenure ({years_with_current}yrs) — possible complacency (+10)")
    elif years_with_current > 20:
        risk_score += 20
        factors.append(f"Very long auditor tenure ({years_with_current}yrs) (+20)")

    # Factor 6: High promoter pledging
    if promoter_pledging_pct > 30:
        risk_score += 10
        factors.append(f"High promoter pledging ({promoter_pledging_pct}%) (+10)")
    if promoter_pledging_pct > 50:
        risk_score += 15
        factors.append(f"Very high promoter pledging ({promoter_pledging_pct}%) (cumulative +25)")

    risk_score = max(0, min(100, risk_score))

    if risk_score <= 20:
        level = "LOW"
    elif risk_score <= 45:
        level = "MODERATE"
    elif risk_score <= 70:
        level = "HIGH"
    else:
        level = "CRITICAL"

    return AuditorRiskScoreResponse(
        risk_score=risk_score,
        risk_level=level,
        is_big4_auditor=is_big4,
        factors=factors,
        explanation="; ".join(factors) if factors else "No red flags detected",
    )


if __name__ == "__main__":
    # Example: Non-Big-4 auditor with qualified opinion
    result = compute_auditor_risk_score(
        current_auditor="XYZ & Associates",
        previous_auditor="PwC",
        regulatory_actions=["SEBI penalty for disclosure lapses"],
        years_with_current=3,
        has_qualified_opinion=True,
        promoter_pledging_pct=35,
    )
    logging.info(result)
