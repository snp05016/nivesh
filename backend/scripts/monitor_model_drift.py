import logging
#!/usr/bin/env python3
"""Monitor confidence calibration drift across the last 100 analyses."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np

def check_confidence_drift():
    try:
        from database import get_session
        from models.analysis import AnalysisReport

        with get_session() as db:
            reports = db.query(AnalysisReport).order_by(
                AnalysisReport.created_at.desc()
            ).limit(100).all()

            confidences = [
                r.calibrated_confidence
                for r in reports
                if r.calibrated_confidence is not None and r.calibrated_confidence > 0
            ]

            if not confidences:
                logging.info("DRIFT CHECK: No calibrated confidence data available yet.")
                return

            mean_conf = float(np.mean(confidences))
            median_conf = float(np.median(confidences))
            std_conf = float(np.std(confidences))

            logging.info(f"Trailing {len(confidences)} analyses:")
            logging.info(f"  Mean confidence: {mean_conf:.3f}")
            logging.info(f"  Median confidence: {median_conf:.3f}")
            logging.info(f"  Std deviation: {std_conf:.3f}")

            if mean_conf > 0.80:
                logging.info("⚠️  WARNING: Overconfidence detected (mean > 0.80). Calibration failure.")
            elif mean_conf < 0.30:
                logging.info("⚠️  WARNING: Underconfidence detected (mean < 0.30). Model degradation.")
            else:
                logging.info("✅ Confidence distribution within acceptable bounds.")
    except Exception as e:
        logging.info(f"DRIFT CHECK ERROR: {e}")

if __name__ == "__main__":
    check_confidence_drift()
