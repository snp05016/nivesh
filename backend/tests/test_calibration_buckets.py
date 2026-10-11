"""
ML-14: calibration buckets are half-open (no double counting), every bucket
statistic uses the same matured subset, small buckets are suppressed, both
dashboards share one bucket scheme, and the horizon is a parameter.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base, AnalysisPrediction
from services.prediction_calibration_service import (
    CONFIDENCE_BUCKETS,
    MIN_BUCKET_N,
    get_calibration_metrics,
)
from services.predictions_performance import _build_bucket_queries


@pytest.fixture()
def Session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture()
def patched(Session):
    @contextmanager
    def _get_session():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    with patch("services.prediction_calibration_service.get_session", _get_session):
        yield Session


def _add(Session, conf, hit30=None, hit7=None, n=1):
    s = Session()
    for _ in range(n):
        s.add(AnalysisPrediction(
            symbol="TCS", recommendation="BULLISH", confidence_pct=conf,
            hit_direction_30d=hit30,
            brier_score_30d=None if hit30 is None else (conf / 100.0 - (1.0 if hit30 else 0.0)) ** 2,
            hit_direction_7d=hit7,
            brier_score_7d=None if hit7 is None else (conf / 100.0 - (1.0 if hit7 else 0.0)) ** 2,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ))
    s.commit()
    s.close()


def _bucket(result, label):
    return next(b for b in result["confidence_buckets"] if b["bucket_label"] == label)


def test_boundary_values_counted_exactly_once(patched):
    for conf in (50, 60, 70, 100):
        _add(patched, conf, hit30=True)

    result = get_calibration_metrics()
    counts = {b["bucket_label"]: b["count"] for b in result["confidence_buckets"]}

    assert sum(counts.values()) == 4
    assert counts["50-60%"] == 1
    assert counts["60-70%"] == 1
    assert counts["70-80%"] == 1
    assert counts["90-100%"] == 1  # 100 belongs to the top bucket
    assert counts["0-50%"] == 0


def test_unmatured_rows_do_not_move_calibration(patched):
    _add(patched, 72, hit30=True, n=8)
    _add(patched, 72, hit30=False, n=4)
    before = get_calibration_metrics()
    b_before = _bucket(before, "70-80%")
    assert b_before["suppressed"] is False
    assert b_before["accuracy"] == pytest.approx(8 / 12, abs=1e-4)
    assert b_before["ci_low"] < b_before["accuracy"] < b_before["ci_high"]

    # Unmatured rows in the same bucket and in another one.
    _add(patched, 79, n=5)
    _add(patched, 95, n=3)
    after = get_calibration_metrics()
    b_after = _bucket(after, "70-80%")

    assert b_after["avg_confidence_pct"] == b_before["avg_confidence_pct"] == pytest.approx(72.0)
    assert b_after["accuracy"] == b_before["accuracy"]
    assert b_after["count"] == 12
    assert b_after["total_count"] == 17
    assert _bucket(after, "90-100%")["total_count"] == 3
    assert after["expected_calibration_error"] == before["expected_calibration_error"]
    assert after["max_calibration_error"] == before["max_calibration_error"]


def test_small_bucket_is_suppressed(patched):
    assert MIN_BUCKET_N > 5
    _add(patched, 85, hit30=True, n=5)

    b = _bucket(get_calibration_metrics(), "80-90%")
    assert b["count"] == 5
    assert b["suppressed"] is True
    assert b["accuracy"] is None
    assert b["overconfidence"] is None
    assert b["ci_low"] is None and b["ci_high"] is None


def test_performance_dashboard_uses_same_buckets(patched):
    for conf in (50, 60, 70, 100):
        _add(patched, conf, hit30=True)
    _add(patched, 60)  # unmatured

    s = patched()
    try:
        rows = _build_bucket_queries(s)
    finally:
        s.close()

    assert [r["bucket_label"] for r in rows] == [label for _, _, label in CONFIDENCE_BUCKETS]
    assert sum(r["count"] for r in rows) == 5
    by_label = {r["bucket_label"]: r for r in rows}
    assert by_label["60-70%"]["count"] == 2
    assert by_label["60-70%"]["matured_count"] == 1
    assert by_label["60-70%"]["hit_rate_30d"] == 1.0


def test_horizon_selects_outcome_columns(patched):
    _add(patched, 72, hit7=True, n=10)  # only the 7d outcome has matured

    b7 = _bucket(get_calibration_metrics(horizon="7d"), "70-80%")
    b30 = _bucket(get_calibration_metrics(horizon="30d"), "70-80%")

    assert b7["count"] == 10 and b7["accuracy"] == 1.0
    assert b30["count"] == 0 and b30["accuracy"] is None
    with pytest.raises(ValueError):
        get_calibration_metrics(horizon="20d")
