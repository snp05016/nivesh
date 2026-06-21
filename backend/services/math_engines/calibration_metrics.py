"""
Calibration diagnostics engine — Brier Score + Expected Calibration Error (ECE).

Computes reliability metrics over resolved AnalysisHistory rows:
  - Brier Score: mean squared error of probability forecasts vs binary outcomes
  - ECE (binned): weighted average gap between predicted confidence and
    observed accuracy across equal-width bins

These are DIAGNOSTIC — they measure whether the system's confidence numbers
are well-calibrated, but do not modify them. Surfaced in payload.

Cold-start guard: returns insufficient_data when sample < MIN_SAMPLES.
"""
from __future__ import annotations
import logging
from typing import Any

from services.math_engines.protocol import InferenceEngine

logger = logging.getLogger(__name__)

MIN_SAMPLES = 30


class CalibrationMetricsEngine(InferenceEngine):

    @classmethod
    def name(cls) -> str:
        return "calibration_metrics"

    @classmethod
    def tags(cls) -> set[str]:
        return {"risk_metric", "calibration"}

    def compute(self, ticker: str, data: dict, session: Any = None) -> dict:
        """Compute Brier Score and ECE from resolved AnalysisHistory.

        data keys:
          - n_bins (int, default 10): ECE bin count
          - ticker_only (bool, default False): filter to this ticker only
        """
        if session is None:
            return {"status": "error", "error": "DB session required"}

        try:
            from database import AnalysisHistory
            import numpy as np

            n_bins = data.get("n_bins", 10)
            ticker_only = data.get("ticker_only", False)

            query = session.query(
                AnalysisHistory.calibrated_confidence,
                AnalysisHistory.was_correct,
            ).filter(
                AnalysisHistory.was_correct.isnot(None),
                AnalysisHistory.calibrated_confidence.isnot(None),
                AnalysisHistory.calibrated_confidence > 0,
            )

            if ticker_only:
                query = query.filter(AnalysisHistory.ticker == ticker.upper())

            rows = query.all()

            if len(rows) < MIN_SAMPLES:
                return {
                    "status": "insufficient_data",
                    "output": {
                        "sample_size": len(rows),
                        "min_required": MIN_SAMPLES,
                        "brier_score": None,
                        "ece": None,
                    },
                }

            predicted = np.array([float(r[0]) for r in rows], dtype=np.float64)
            actual = np.array([1.0 if r[1] else 0.0 for r in rows], dtype=np.float64)

            # Brier Score: mean((p - o)^2)
            brier = float(np.mean((predicted - actual) ** 2))

            # ECE: sum over bins of (|avg_predicted - avg_actual| * bin_weight)
            bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
            ece = 0.0
            bin_details = []
            for i in range(n_bins):
                mask = (predicted >= bin_edges[i]) & (predicted < bin_edges[i + 1])
                if i == n_bins - 1:  # include right edge in last bin
                    mask = (predicted >= bin_edges[i]) & (predicted <= bin_edges[i + 1])
                count = int(mask.sum())
                if count == 0:
                    continue
                avg_pred = float(predicted[mask].mean())
                avg_actual = float(actual[mask].mean())
                weight = count / len(predicted)
                gap = abs(avg_pred - avg_actual)
                ece += gap * weight
                bin_details.append({
                    "bin": f"{bin_edges[i]:.2f}-{bin_edges[i+1]:.2f}",
                    "count": count,
                    "avg_predicted": round(avg_pred, 4),
                    "avg_actual": round(avg_actual, 4),
                    "gap": round(gap, 4),
                })

            return {
                "status": "ok",
                "output": {
                    "brier_score": round(brier, 6),
                    "ece": round(ece, 6),
                    "sample_size": len(rows),
                    "interpretation": _interpret(brier, ece),
                    "reliability_bins": bin_details,
                },
            }

        except Exception as e:
            logger.warning("[calibration_metrics] error: %s", e)
            return {"status": "error", "error": str(e)}


def _interpret(brier: float, ece: float) -> str:
    """Human-readable interpretation of calibration quality."""
    if brier < 0.15 and ece < 0.05:
        return "Well-calibrated: predicted probabilities closely match observed outcomes."
    elif brier < 0.25 and ece < 0.10:
        return "Moderately calibrated: some drift between predicted and observed rates."
    else:
        return "Poorly calibrated: significant gap between confidence and actual accuracy."
