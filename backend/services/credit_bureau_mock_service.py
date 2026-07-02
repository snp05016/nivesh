"""Credit Bureau MOCK service.

MOCK DATA — simulated for demo purposes, not a real integration.
This module does NOT call any real credit bureau (CIBIL/Experian/Equifax/
CRIF High Mark). It deterministically derives a CIBIL-style score (300-900)
from a user's id so the loan marketplace demo has stable, repeatable
"credit scores" to underwrite mock loan applications against. Do NOT use
this for real lending decisions.
"""
import hashlib

CREDIT_SCORE_MIN = 300
CREDIT_SCORE_MAX = 900
_CREDIT_SCORE_RANGE = CREDIT_SCORE_MAX - CREDIT_SCORE_MIN


def get_mock_credit_score(user_id: int) -> int:
    """Deterministically derive a MOCK CIBIL-style credit score (300-900) for a user.

    MOCK DATA — not a real credit bureau integration, do not use for real
    lending decisions. The score is a pure function of user_id (seeded via a
    stable hash), so the same user always gets the same mock score, but the
    "distribution" across users looks plausible for a demo.
    """
    digest = hashlib.sha256(f"nivesh-mock-credit-bureau-{user_id}".encode("utf-8")).hexdigest()
    # Use the first 8 hex chars as a deterministic 32-bit integer seed.
    seed = int(digest[:8], 16)
    score = CREDIT_SCORE_MIN + (seed % (_CREDIT_SCORE_RANGE + 1))
    return score


def get_mock_credit_report_summary(user_id: int) -> dict:
    """Return a small MOCK credit report summary for display in the loan
    marketplace UI (score + a couple of derived, clearly-fake fields).

    MOCK DATA — simulated for demo purposes, not a real credit bureau integration.
    """
    score = get_mock_credit_score(user_id)
    if score >= 750:
        band = "excellent"
    elif score >= 650:
        band = "good"
    elif score >= 550:
        band = "fair"
    else:
        band = "poor"

    return {
        "user_id": user_id,
        "credit_score": score,
        "score_band": band,
        "bureau_name": "MOCK Bureau (demo only — not a real CIBIL/Experian/Equifax integration)",
        "score_range_min": CREDIT_SCORE_MIN,
        "score_range_max": CREDIT_SCORE_MAX,
    }
