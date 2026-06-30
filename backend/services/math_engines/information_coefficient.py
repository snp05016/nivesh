"""
Information Coefficient (IC) / Rank IC engine.

Computes Spearman rank correlation between a predictive factor
(calibrated_confidence) and realised outcomes (outcome_delta_pct)
across resolved AnalysisHistory rows.

IC > 0 means the confidence signal has predictive power.
IC ~ 0 means random. IC < 0 means systematically wrong.

Diagnostic only — surfaced in payload, does not modify confidence.
Cold-start guard: MIN_SAMPLES.
"""
from __future__ import annotations
import logging
from typing import Any, Optional, List, Dict
from pydantic import BaseModel

class ICOutput(BaseModel):
    rank_ic: Optional[float] = None
    p_value: Optional[float] = None
    sample_size: int
    min_required: Optional[int] = None
    significant: Optional[bool] = None
    interpretation: Optional[str] = None

class InformationCoefficientResponse(BaseModel):
    status: str
    output: Optional[ICOutput] = None
    error: Optional[str] = None

from services.math_engines.protocol import InferenceEngine

logger = logging.getLogger(__name__)

MIN_SAMPLES = 30


class InformationCoefficientEngine(InferenceEngine):

    @classmethod
    def name(cls) -> str:
        return "information_coefficient"

    @classmethod
    def tags(cls) -> set[str]:
        return {"risk_metric", "calibration"}

    def compute(self, ticker: str, data: dict, session: Any = None) -> InformationCoefficientResponse:
        if session is None:
            return InformationCoefficientResponse(status="error", error="DB session required")

        try:
            from database import AnalysisHistory
            from scipy.stats import spearmanr
            import numpy as np

            ticker_only = data.get("ticker_only", False)

            query = session.query(
                AnalysisHistory.calibrated_confidence,
                AnalysisHistory.outcome_delta_pct,
            ).filter(
                AnalysisHistory.outcome_delta_pct.isnot(None),
                AnalysisHistory.calibrated_confidence.isnot(None),
                AnalysisHistory.calibrated_confidence > 0,
            )

            if ticker_only:
                query = query.filter(AnalysisHistory.ticker == ticker.upper())

            rows = query.all()

            if len(rows) < MIN_SAMPLES:
                return InformationCoefficientResponse(
                    status="insufficient_data",
                    output=ICOutput(
                        rank_ic=None,
                        p_value=None,
                        sample_size=len(rows),
                        min_required=MIN_SAMPLES,
                    ),
                )

            factor = np.array([float(r[0]) for r in rows], dtype=np.float64)
            outcome = np.array([float(r[1]) for r in rows], dtype=np.float64)

            corr, p_value = spearmanr(factor, outcome)

            return InformationCoefficientResponse(
                status="ok",
                output=ICOutput(
                    rank_ic=round(float(corr), 6),
                    p_value=round(float(p_value), 6),
                    sample_size=len(rows),
                    significant=float(p_value) < 0.05,
                    interpretation=_interpret_ic(float(corr), float(p_value)),
                ),
            )

        except Exception as e:
            logger.warning("[information_coefficient] error: %s", e)
            return InformationCoefficientResponse(status="error", error=str(e))


def _interpret_ic(ic: float, p_value: float) -> str:
    if p_value >= 0.05:
        return "Not statistically significant — confidence signal may not yet be predictive."
    if ic > 0.1:
        return f"Positive IC ({ic:.3f}): confidence signal has meaningful predictive power."
    elif ic > 0.02:
        return f"Weak positive IC ({ic:.3f}): slight predictive edge, needs more data."
    elif ic > -0.02:
        return f"Near-zero IC ({ic:.3f}): confidence has no predictive relationship with outcomes."
    else:
        return f"Negative IC ({ic:.3f}): confidence is inversely correlated — calibration may be needed."
