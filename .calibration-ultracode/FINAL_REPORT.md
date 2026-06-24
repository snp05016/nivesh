# Prediction Calibration System -- Final Build Report

**Date:** 2026-06-24
**Branch:** main
**Total lines added:** ~3,048 across 8 files
**Total test count:** 42

---

## Files Changed

| File | Status | Lines | Purpose |
|------|--------|-------|---------|
| `backend/schemas/prediction_calibration.py` | NEW | 90 | Pydantic response models for calibration, pillar attribution, and model version endpoints |
| `backend/services/prediction_calibration_service.py` | NEW | 611 | Core calibration math: ECE, MCE, bucket accuracy, pillar correlation, model version grouping |
| `backend/routers/predictions.py` | MODIFIED | 151 | Added 3 new GET endpoints to existing predictions router |
| `backend/tests/test_prediction_calibration_service.py` | NEW | 659 | 13 tests covering bucket math, ECE, MCE, overconfidence detection, empty DB edge cases |
| `backend/tests/test_prediction_calibration_api.py` | NEW | 434 | 13 tests covering endpoint response schemas, auth requirements, empty DB responses |
| `backend/tests/test_prediction_pillar_attribution.py` | NEW | 322 | 7 tests covering point-biserial correlation, missing-rate tracking, pillar ranking |
| `backend/tests/test_prediction_model_versions.py` | NEW | 314 | 9 tests covering model version grouping, hit rate computation, calibration error per version |
| `backend/docs/PREDICTION_CALIBRATION_SYSTEM.md` | NEW | 467 | Full system documentation: architecture, formulas, usage guide, data flow |

---

## Migrations Added

None needed. All required columns already exist on the `AnalysisPrediction` ORM model:

- `fused_confidence`, `confidence_direction`, `confidence_horizon`
- `ta_confidence`, `fundamental_confidence`, `sentiment_confidence`, `risk_confidence`, `momentum_confidence`
- `actual_return_7d`, `actual_return_30d`, `actual_return_90d`
- `hit_direction_7d`, `hit_direction_30d`, `hit_direction_90d`
- `model_version`

These columns were added in prior commits (`e1e7f04`, `1fb86c2`).

---

## Endpoints Added

### 1. GET `/api/v1/predictions/calibration`

Returns calibration analytics bucketed by confidence decile.

**Query params:** `horizon` (7d/30d/90d, default 30d), `sector` (optional filter)

**Response includes:**
- `buckets[]` -- per-decile accuracy, avg confidence, count, overconfident flag
- `ece` -- Expected Calibration Error (weighted mean of |accuracy - confidence| per bucket)
- `mce` -- Maximum Calibration Error (worst single bucket)
- `total_predictions`, `matured_predictions`
- `overconfidence_zones[]` -- buckets where confidence exceeds accuracy by >10pp

### 2. GET `/api/v1/predictions/pillar-attribution`

Returns per-pillar predictive lift analysis.

**Query params:** `horizon` (7d/30d/90d, default 30d)

**Response includes:**
- `pillars[]` -- for each of ta, fundamental, sentiment, risk, momentum:
  - `point_biserial_r` -- correlation with binary hit outcome
  - `mean_when_hit`, `mean_when_miss` -- average pillar confidence split by outcome
  - `missing_rate` -- fraction of predictions where pillar was null
  - `predictive_rank` -- 1 = most predictive pillar
- `best_pillar`, `worst_pillar`

### 3. GET `/api/v1/predictions/model-versions`

Returns model version comparison analytics.

**Query params:** `horizon` (7d/30d/90d, default 30d)

**Response includes:**
- `versions[]` -- for each model_version string:
  - `hit_rate`, `mean_confidence`, `calibration_error`
  - `prediction_count`, `matured_count`
  - `date_range` (first/last prediction timestamp)
- `best_version` -- version with lowest calibration error (min 10 matured)

---

## Tests Added

| Test file | Count | Coverage area |
|-----------|-------|---------------|
| `test_prediction_calibration_service.py` | 13 | Bucket construction, ECE/MCE formulas, overconfidence detection, sector filtering, empty DB, single-prediction edge case |
| `test_prediction_calibration_api.py` | 13 | Endpoint HTTP status, response schema validation, auth enforcement, empty DB 200 response, horizon parameter handling |
| `test_prediction_pillar_attribution.py` | 7 | Point-biserial correlation math, missing rate calculation, pillar ranking, empty DB, all-null pillars |
| `test_prediction_model_versions.py` | 9 | Version grouping, hit rate per version, calibration error per version, best_version selection, empty DB |
| **Total** | **42** | |

---

## Commands Run

- Inspected `backend/models/db_models.py` -- confirmed all required columns present on `AnalysisPrediction`
- Inspected `backend/database.py` -- confirmed `get_session()` context manager pattern
- Inspected existing `backend/routers/predictions.py` -- confirmed router prefix and auth pattern
- Inspected `backend/services/confidence_fusion.py` -- confirmed pillar column names
- Inspected `backend/services/outcome_tracker.py` -- confirmed outcome column naming convention
- No Alembic migration generated (no schema changes required)

---

## Unresolved Issues

1. **Remote test execution required.** Per AGENTS.md section 6.5, all backend tests must run on the remote server (`saumyapatel@192.168.1.122`). Tests are written and ready but have not been executed yet.
2. **ECE/MCE values will be null until sufficient predictions mature.** The outcome tracker must run its nightly cycle to populate `actual_return_*` and `hit_direction_*` fields. Until N > 0 matured predictions exist, all calibration endpoints return valid but empty/zero responses.
3. **Point-biserial correlation requires variance in both variables.** If all matured predictions are hits (or all misses), correlation returns null with a warning in the response.

---

## Assumptions Made

1. All confidence pillar columns (`ta_confidence`, `fundamental_confidence`, `sentiment_confidence`, `risk_confidence`, `momentum_confidence`) already exist on `AnalysisPrediction` -- **confirmed by model inspection**.
2. `StockUniverse.sector` is joined for sector-based calibration breakdowns via `ticker_symbol` foreign key.
3. Point-biserial correlation (scipy-free, pure Python implementation) is sufficient for binary outcome correlation against continuous confidence scores.
4. The 30d horizon is the primary calibration horizon (default parameter value).
5. Calibration buckets use decile boundaries: [0,10), [10,20), ..., [90,100].
6. A prediction is "overconfident" when bucket midpoint confidence exceeds bucket accuracy by more than 10 percentage points.
7. `model_version` string format is opaque -- grouping is by exact string match.

---

## Architecture Compliance

| Rule | Status |
|------|--------|
| Controller-Service-Repository (section 3.1) | PASS -- endpoints in router delegate to service; no DB queries in router |
| `get_session()` usage (section 3.2) | PASS -- all DB access via context manager |
| No business logic in routers (section 3.1) | PASS -- all math/aggregation in `prediction_calibration_service.py` |
| Indian numbering (section 5.1) | N/A -- calibration endpoints return raw floats for programmatic consumption |
| Response normalization (section 5.2) | N/A -- no LLM output in calibration pipeline |
| Alembic migration check (section 3.5) | PASS -- no schema changes, no migration needed |

---

## Next Recommended Tasks

1. **Run nightly outcome tracker** to populate `actual_return_*` and `hit_direction_*` fields on existing predictions.
2. **Execute test suite on remote server** per section 6.5 deployment protocol.
3. **Once N > 100 matured predictions exist**, review calibration dashboard for overconfidence patterns and ECE trends.
4. **Use pillar attribution results** to adjust fusion weights in `confidence_fusion.py` -- pillars with higher `point_biserial_r` should receive proportionally higher weight.
5. **Begin LightGBM retraining pipeline** using calibration insights as training signal for confidence recalibration.
6. **Add iOS calibration dashboard view** to surface ECE/MCE and pillar attribution visually (Banknote Aesthetic, Theme tokens, GuillocheDivider separators).
