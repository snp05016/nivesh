"""
Tests for get_model_version_analytics() from prediction_calibration_service.

Uses monkeypatched in-memory SQLite so no production database is touched.
All test data is deterministic with hand-computed expected values.
"""

import pytest
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base, AnalysisPrediction


# ---------------------------------------------------------------------------
# Fixtures — in-memory SQLite session + monkeypatched get_session
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def _patch_get_session(db_session, monkeypatch):
    """Redirect get_session() in the calibration service to our in-memory DB."""

    @contextmanager
    def _mock_get_session():
        yield db_session

    monkeypatch.setattr(
        "services.prediction_calibration_service.get_session",
        _mock_get_session,
    )


def _make_prediction(**overrides) -> AnalysisPrediction:
    """Helper to build an AnalysisPrediction with sensible defaults."""
    defaults = dict(
        symbol="INFY",
        recommendation="BULLISH",
        confidence_pct=70,
        horizon_days=30,
        scan_type="standard",
    )
    defaults.update(overrides)
    return AnalysisPrediction(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVersionGrouping:
    """test_version_grouping — two versions with different counts."""

    def test_version_grouping(self, db_session):
        from services.prediction_calibration_service import get_model_version_analytics

        # v1: 3 predictions, v2: 2 predictions
        for _ in range(3):
            db_session.add(_make_prediction(model_version="v1.0", ml_engine_mode="lgbm_trained"))
        for _ in range(2):
            db_session.add(_make_prediction(model_version="v2.0", ml_engine_mode="fallback_technical_heuristic"))
        db_session.commit()

        result = get_model_version_analytics()

        assert result["total_predictions"] == 5
        versions = result["model_versions"]
        assert len(versions) == 2

        # Ordered by count desc → v1.0 first
        ver_map = {v["model_version"]: v for v in versions}
        assert ver_map["v1.0"]["total_predictions"] == 3
        assert ver_map["v2.0"]["total_predictions"] == 2

        # ml_engine_mode is the most common per version
        assert ver_map["v1.0"]["ml_engine_mode"] == "lgbm_trained"
        assert ver_map["v2.0"]["ml_engine_mode"] == "fallback_technical_heuristic"


class TestHitRatesByVersion:
    """test_hit_rates_by_version — verify hit rates computed correctly per version."""

    def test_hit_rates_by_version(self, db_session):
        from services.prediction_calibration_service import get_model_version_analytics

        # v1.0: 4 predictions, 3 hit on 30d (75%), 2 hit on 7d (50%), 1 hit on 90d (25%)
        hit_configs_v1 = [
            # (hit_7d, hit_30d, hit_90d)
            (True,  True,  True),
            (True,  True,  False),
            (False, True,  False),
            (False, False, False),
        ]
        for h7, h30, h90 in hit_configs_v1:
            db_session.add(_make_prediction(
                model_version="v1.0",
                hit_direction_7d=h7,
                hit_direction_30d=h30,
                hit_direction_90d=h90,
            ))

        # v2.0: 2 predictions, both hit on all horizons (100%)
        for _ in range(2):
            db_session.add(_make_prediction(
                model_version="v2.0",
                hit_direction_7d=True,
                hit_direction_30d=True,
                hit_direction_90d=True,
            ))
        db_session.commit()

        result = get_model_version_analytics()
        ver_map = {v["model_version"]: v for v in result["model_versions"]}

        # v1.0 hit rates
        assert ver_map["v1.0"]["hit_rate_7d"] == pytest.approx(0.5, abs=0.001)
        assert ver_map["v1.0"]["hit_rate_30d"] == pytest.approx(0.75, abs=0.001)
        assert ver_map["v1.0"]["hit_rate_90d"] == pytest.approx(0.25, abs=0.001)

        # v2.0 hit rates — all 100%
        assert ver_map["v2.0"]["hit_rate_7d"] == pytest.approx(1.0, abs=0.001)
        assert ver_map["v2.0"]["hit_rate_30d"] == pytest.approx(1.0, abs=0.001)
        assert ver_map["v2.0"]["hit_rate_90d"] == pytest.approx(1.0, abs=0.001)


class TestConfidenceAvgComputation:
    """test_confidence_avg_computation — verify average confidence per version."""

    def test_confidence_avg_computation(self, db_session):
        from services.prediction_calibration_service import get_model_version_analytics

        # v1.0: confidences 60, 70, 80 → avg = 70.0
        for c in (60, 70, 80):
            db_session.add(_make_prediction(model_version="v1.0", confidence_pct=c))

        # v2.0: confidences 90, 50 → avg = 70.0
        for c in (90, 50):
            db_session.add(_make_prediction(model_version="v2.0", confidence_pct=c))
        db_session.commit()

        result = get_model_version_analytics()
        ver_map = {v["model_version"]: v for v in result["model_versions"]}

        assert ver_map["v1.0"]["confidence_avg"] == pytest.approx(70.0, abs=0.01)
        assert ver_map["v2.0"]["confidence_avg"] == pytest.approx(70.0, abs=0.01)


class TestCalibrationErrorPerVersion:
    """test_calibration_error_per_version — verify |hit_rate - avg_conf/100|."""

    def test_calibration_error_per_version(self, db_session):
        from services.prediction_calibration_service import get_model_version_analytics

        # v1.0: confidence 80 for all, hit_direction_30d: True, True, False, False → hit_rate=0.5
        # cal_err = |0.5 - 80/100| = |0.5 - 0.8| = 0.3
        for hit in (True, True, False, False):
            db_session.add(_make_prediction(
                model_version="v1.0",
                confidence_pct=80,
                hit_direction_30d=hit,
            ))

        # v2.0: confidence 60 for all, hit_direction_30d: True, True, True → hit_rate=1.0
        # cal_err = |1.0 - 60/100| = |1.0 - 0.6| = 0.4
        for _ in range(3):
            db_session.add(_make_prediction(
                model_version="v2.0",
                confidence_pct=60,
                hit_direction_30d=True,
            ))
        db_session.commit()

        result = get_model_version_analytics()
        ver_map = {v["model_version"]: v for v in result["model_versions"]}

        assert ver_map["v1.0"]["calibration_error_30d"] == pytest.approx(0.3, abs=0.001)
        assert ver_map["v2.0"]["calibration_error_30d"] == pytest.approx(0.4, abs=0.001)


class TestConfidenceRealizedGap:
    """test_confidence_realized_gap — verify gap = avg_conf/100 - hit_rate."""

    def test_confidence_realized_gap_overconfident(self, db_session):
        """Overconfident model: high confidence, low hit rate → positive gap."""
        from services.prediction_calibration_service import get_model_version_analytics

        # v1.0: confidence 90, hit_direction_30d: True, False, False, False → hit_rate=0.25
        # gap = 90/100 - 0.25 = 0.65  (overconfident)
        for hit in (True, False, False, False):
            db_session.add(_make_prediction(
                model_version="v1.0",
                confidence_pct=90,
                hit_direction_30d=hit,
            ))
        db_session.commit()

        result = get_model_version_analytics()
        ver_map = {v["model_version"]: v for v in result["model_versions"]}

        assert ver_map["v1.0"]["confidence_realized_accuracy_gap"] == pytest.approx(0.65, abs=0.001)

    def test_confidence_realized_gap_underconfident(self, db_session):
        """Underconfident model: low confidence, high hit rate → negative gap."""
        from services.prediction_calibration_service import get_model_version_analytics

        # v1.0: confidence 40, hit_direction_30d: True, True, True → hit_rate=1.0
        # gap = 40/100 - 1.0 = -0.6  (underconfident)
        for _ in range(3):
            db_session.add(_make_prediction(
                model_version="v1.0",
                confidence_pct=40,
                hit_direction_30d=True,
            ))
        db_session.commit()

        result = get_model_version_analytics()
        ver_map = {v["model_version"]: v for v in result["model_versions"]}

        assert ver_map["v1.0"]["confidence_realized_accuracy_gap"] == pytest.approx(-0.6, abs=0.001)

    def test_gap_is_none_without_hit_data(self, db_session):
        """When no hit_direction_30d data exists, gap should be None."""
        from services.prediction_calibration_service import get_model_version_analytics

        db_session.add(_make_prediction(model_version="v1.0", confidence_pct=75))
        db_session.commit()

        result = get_model_version_analytics()
        ver_map = {v["model_version"]: v for v in result["model_versions"]}

        assert ver_map["v1.0"]["confidence_realized_accuracy_gap"] is None
        assert ver_map["v1.0"]["calibration_error_30d"] is None


class TestEmptyDatabase:
    """test_empty_database — no crash, empty versions list."""

    def test_empty_database(self, db_session):
        from services.prediction_calibration_service import get_model_version_analytics

        result = get_model_version_analytics()

        assert result["total_predictions"] == 0
        assert result["model_versions"] == []


class TestSingleVersion:
    """test_single_version — one version with fully known stats."""

    def test_single_version(self, db_session):
        from services.prediction_calibration_service import get_model_version_analytics

        # 5 predictions, all v1.0, confidence 70
        # hit_direction_30d: T, T, T, F, None → 3 non-null, 3 hits out of 4 non-null? No.
        # Let's be precise: 4 with hit data, 1 without
        # Hits: T, T, T, F → hit_rate = 3/4 = 0.75
        # actual_return_30d: 5.0, 3.0, -1.0, -2.0, 10.0 → avg = 3.0
        # brier_score_30d: 0.1, 0.2, 0.3, 0.4, None → avg of 4 = 0.25
        configs = [
            dict(hit_direction_30d=True,  actual_return_30d=5.0,  brier_score_30d=0.1),
            dict(hit_direction_30d=True,  actual_return_30d=3.0,  brier_score_30d=0.2),
            dict(hit_direction_30d=True,  actual_return_30d=-1.0, brier_score_30d=0.3),
            dict(hit_direction_30d=False, actual_return_30d=-2.0, brier_score_30d=0.4),
            dict(hit_direction_30d=None,  actual_return_30d=10.0, brier_score_30d=None),
        ]
        for cfg in configs:
            db_session.add(_make_prediction(
                model_version="v1.0",
                ml_engine_mode="lgbm_trained",
                confidence_pct=70,
                **cfg,
            ))
        db_session.commit()

        result = get_model_version_analytics()

        assert result["total_predictions"] == 5
        assert len(result["model_versions"]) == 1

        v = result["model_versions"][0]
        assert v["model_version"] == "v1.0"
        assert v["ml_engine_mode"] == "lgbm_trained"
        assert v["total_predictions"] == 5

        # hit_rate_30d: 3 hits / 4 non-null = 0.75
        assert v["hit_rate_30d"] == pytest.approx(0.75, abs=0.001)

        # average_return_30d: (5+3-1-2+10)/5 = 3.0
        assert v["average_return_30d"] == pytest.approx(3.0, abs=0.01)

        # brier_score_30d: (0.1+0.2+0.3+0.4)/4 = 0.25
        # Note: avg is over non-null brier values (SQLAlchemy avg ignores NULLs)
        assert v["brier_score_30d"] == pytest.approx(0.25, abs=0.01)

        # confidence_avg: all 70 → 70.0
        assert v["confidence_avg"] == pytest.approx(70.0, abs=0.01)

        # calibration_error_30d: |0.75 - 70/100| = |0.75 - 0.70| = 0.05
        assert v["calibration_error_30d"] == pytest.approx(0.05, abs=0.001)

        # confidence_realized_accuracy_gap: 70/100 - 0.75 = -0.05 (slightly underconfident)
        assert v["confidence_realized_accuracy_gap"] == pytest.approx(-0.05, abs=0.001)
