# Nivesh Prediction Logging & Outcome Tracking Audit Report

**Date:** June 24, 2026
**Status:** Corrected 2026-10-11: the outcome job was never scheduled (it existed only as an undeployed Celery task), so no outcome labels were written until the `prediction_outcomes` APScheduler job was added (audit package w5-01, ML-03).

This document confirms the completion of a full structural audit of the Nivesh prediction logging feedback loop, ensuring that all AI/Quant predictions are meticulously stored and tracked to build training datasets for LightGBM.

## 1. Audit Verification Checklist

| Requirement | Status | Notes |
| :--- | :---: | :--- |
| **1. Every analysis creates an `analysis_predictions` row** | ✅ | Verified inside `orchestrator.py` via `analyze()` block. Guaranteed execution before return. |
| **2. Final fused confidence is stored** | ✅ | Mapped perfectly to `confidence_pct` (0-100). |
| **3. All confidence pillars stored separately** | ✅ | `llm_confidence`, `quant_confidence`, `venn_abers_confidence`, `signal_agreement`, `ml_confidence` are isolated. |
| **4. `entry_price` is captured correctly** | ✅ | Derived safely from `current_price_inr`. |
| **5. 7D/30D/90D outcome fields exist** | ✅ | `actual_return_7d`, `actual_return_30d`, and `actual_return_90d` fully verified. |
| **6. Brier score fields exist** | ✅ | *Remediated*. Expanded single field to `brier_score_7d`, `brier_score_30d`, and `brier_score_90d` (with corresponding `hit_direction` flags). |
| **7. Context fields stored** | ✅ | *Remediated*. Added missing `scan_type` and `regime_id` fields to DB, alongside `model_version` and `ml_engine_mode`. |
| **8. Tracker updates old predictions safely** | ✅ | *Remediated*. Expanded `yfinance` fetch from 6 months to 2 years to ensure oldest predictions still resolve their `entry_price` backwards. |
| **9. Missing Alembic migrations added** | ✅ | Migration `8b42e94256d6` successfully tracked and applied schema alterations. |
| **10. Tests for logging and tracking** | ✅ | `test_prediction_logging.py` & `test_outcome_tracker.py` added. Suite passes 100%. |

## 2. Engineering Upgrades Executed

During the audit, the following structural enhancements were proactively applied:

1. **Multi-Horizon Brier Scoring**: Previously, the system only assigned a Brier score at the 30-day mark. The schema and `outcome_tracker.py` were upgraded to assign individual hit directions and Brier scores at the 7-day, 30-day, and 90-day intervals. This allows ML engineers to evaluate if a given prediction engine is more accurate in the short vs. long term.
2. **Context Retention**: We added `scan_type` and `regime_id` directly to the `analysis_predictions` table. When building future LightGBM models, we can now slice historical accuracy based on whether the market was in a `BULL_HIGH_VOL` vs `BEAR_LOW_VOL` regime at the time of the prediction.

## 3. The Live ML Feedback Loop
With this audit complete, the system functions as a closed loop:
1. `orchestrator.py` mathematically computes a fused prediction.
2. It explicitly logs all deterministic components to SQLite/Postgres.
3. The nightly APScheduler job `prediction_outcomes` (21:10 UTC, `harvest_worker._run_prediction_outcomes` -> `outcome_tracker.update_prediction_outcomes`) polls `yfinance`, checks actual market reality, and calculates the mathematical penalty (`(confidence - outcome)^2`). Its last run is reported as `last_outcome_run` by `GET /api/v1/predictions/calibration/health`.
4. This results in a continuously growing dataset of perfectly formatted, labeled rows ready for ML alpha model training in `ml-engine`.
