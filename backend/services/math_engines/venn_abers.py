"""
Venn-Abers-style isotonic calibration engine.

Fits sklearn's IsotonicRegression on historical
(predicted_confidence, was_correct) pairs from AnalysisHistory,
producing a calibrated probability point estimate + [p_lo, p_hi]
Venn-Abers bracket.

The bracket is computed by fitting two isotonic regressions:
  p_lo: isotonic fit treating the new prediction as outcome=0
  p_hi: isotonic fit treating the new prediction as outcome=1
The interval [p_lo, p_hi] brackets the true calibrated probability
regardless of the new observation's actual outcome.

Cold-start guard: returns status=insufficient_data when sample < MIN_SAMPLES,
falling back to the raw uncalibrated confidence.
"""
from __future__ import annotations
import logging
from typing import Any

from services.math_engines.protocol import InferenceEngine

logger = logging.getLogger(__name__)

MIN_SAMPLES = 30


class VennAbersEngine(InferenceEngine):

    @classmethod
    def name(cls) -> str:
        return "venn_abers_calibration"

    @classmethod
    def tags(cls) -> set[str]:
        return {"confidence_modifier", "calibration"}

    def compute(self, ticker: str, data: dict, session: Any = None) -> dict:
        """Calibrate a raw confidence value using historical labeled outcomes.

        data keys:
          - raw_confidence (float, required): the uncalibrated confidence 0-1
          - ticker_only (bool, default False): restrict training data to this ticker
        """
        raw_conf = data.get("raw_confidence")
        if raw_conf is None:
            return {"status": "error", "error": "raw_confidence required in data"}

        if session is None:
            return {"status": "error", "error": "DB session required"}

        try:
            from database import AnalysisHistory
            import numpy as np
            from sklearn.isotonic import IsotonicRegression

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
                        "calibrated_confidence": float(raw_conf),
                        "confidence_interval": [float(raw_conf), float(raw_conf)],
                        "sample_size": len(rows),
                        "min_required": MIN_SAMPLES,
                        "method": "passthrough",
                    },
                }

            X = np.array([float(r[0]) for r in rows], dtype=np.float64)
            y = np.array([1.0 if r[1] else 0.0 for r in rows], dtype=np.float64)

            # Primary isotonic fit: calibrated point estimate
            iso = IsotonicRegression(y_min=0.05, y_max=0.95, out_of_bounds="clip")
            iso.fit(X, y)
            calibrated = float(iso.predict([float(raw_conf)])[0])

            # Venn-Abers bracket: fit with augmented datasets
            # p_lo: add (raw_conf, 0) — pessimistic
            X_lo = np.append(X, float(raw_conf))
            y_lo = np.append(y, 0.0)
            iso_lo = IsotonicRegression(y_min=0.05, y_max=0.95, out_of_bounds="clip")
            iso_lo.fit(X_lo, y_lo)
            p_lo = float(iso_lo.predict([float(raw_conf)])[0])

            # p_hi: add (raw_conf, 1) — optimistic
            X_hi = np.append(X, float(raw_conf))
            y_hi = np.append(y, 1.0)
            iso_hi = IsotonicRegression(y_min=0.05, y_max=0.95, out_of_bounds="clip")
            iso_hi.fit(X_hi, y_hi)
            p_hi = float(iso_hi.predict([float(raw_conf)])[0])

            return {
                "status": "ok",
                "output": {
                    "raw_confidence": round(float(raw_conf), 4),
                    "calibrated_confidence": round(calibrated, 4),
                    "confidence_interval": [round(min(p_lo, p_hi), 4), round(max(p_lo, p_hi), 4)],
                    "sample_size": len(rows),
                    "method": "venn_abers_isotonic",
                    "calibration_shift": round(calibrated - float(raw_conf), 4),
                },
            }

        except Exception as e:
            logger.warning("[venn_abers] error: %s", e)
            return {"status": "error", "error": str(e)}
