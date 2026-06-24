"""
Tests for pillar attribution analytics (get_pillar_attribution).

Uses monkeypatched in-memory SQLite DB to verify correlation computation,
missing-rate tracking, usefulness ranking, predictive lift, and bucketed
accuracy for each confidence pillar.
"""

import pytest
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base, AnalysisPrediction
from services.prediction_calibration_service import (
    get_pillar_attribution,
    PILLAR_COLUMNS,
    _point_biserial,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mem_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(mem_engine):
    Session = sessionmaker(bind=mem_engine)
    sess = Session()
    yield sess
    sess.close()


@pytest.fixture
def patch_session(monkeypatch, session):
    """Replace get_session in the service module with one backed by the in-memory DB."""

    @contextmanager
    def _mock_get_session():
        yield session

    monkeypatch.setattr(
        "services.prediction_calibration_service.get_session",
        _mock_get_session,
    )


def _make_prediction(
    symbol="TEST",
    recommendation="BULLISH",
    confidence_pct=70,
    llm_confidence=70.0,
    quant_confidence=0.7,
    ml_confidence=None,
    venn_abers_confidence=0.7,
    signal_agreement=0.7,
    hit_direction_30d=True,
    brier_score_30d=0.04,
    **overrides,
) -> AnalysisPrediction:
    kwargs = dict(
        symbol=symbol,
        recommendation=recommendation,
        confidence_pct=confidence_pct,
        llm_confidence=llm_confidence,
        quant_confidence=quant_confidence,
        ml_confidence=ml_confidence,
        venn_abers_confidence=venn_abers_confidence,
        signal_agreement=signal_agreement,
        hit_direction_30d=hit_direction_30d,
        brier_score_30d=brier_score_30d,
    )
    kwargs.update(overrides)
    return AnalysisPrediction(**kwargs)


# ---------------------------------------------------------------------------
# 1. test_all_pillars_present
# ---------------------------------------------------------------------------

def test_all_pillars_present(session, patch_session):
    """get_pillar_attribution returns exactly the 5 configured pillar keys."""
    session.add(_make_prediction())
    session.commit()

    result = get_pillar_attribution()

    assert result["total_predictions"] == 1
    assert set(result["pillars"].keys()) == set(PILLAR_COLUMNS)
    assert len(result["pillars"]) == 5


# ---------------------------------------------------------------------------
# 2. test_correlation_direction
# ---------------------------------------------------------------------------

def test_correlation_direction(session, patch_session):
    """
    When llm_confidence is high on hits and low on misses,
    the point-biserial correlation should be positive.
    """
    # High confidence -> hit
    for _ in range(10):
        session.add(_make_prediction(
            llm_confidence=90.0,
            confidence_pct=80,
            hit_direction_30d=True,
        ))
    # Low confidence -> miss
    for _ in range(10):
        session.add(_make_prediction(
            llm_confidence=30.0,
            confidence_pct=40,
            hit_direction_30d=False,
        ))
    session.commit()

    result = get_pillar_attribution()
    llm_corr = result["pillars"]["llm_confidence"]["correlation_with_hit_30d"]

    assert llm_corr is not None
    assert llm_corr > 0, f"Expected positive correlation, got {llm_corr}"


# ---------------------------------------------------------------------------
# 3. test_missing_rate_computation
# ---------------------------------------------------------------------------

def test_missing_rate_computation(session, patch_session):
    """Insert 10 rows; 3 have ml_confidence=None -> missing_rate=0.3."""
    for i in range(10):
        ml_val = None if i < 3 else 0.5 + i * 0.02
        session.add(_make_prediction(ml_confidence=ml_val))
    session.commit()

    result = get_pillar_attribution()
    ml_missing = result["pillars"]["ml_confidence"]["missing_rate"]

    assert ml_missing == pytest.approx(0.3, abs=1e-4)


# ---------------------------------------------------------------------------
# 4. test_usefulness_rank_ordering
# ---------------------------------------------------------------------------

def test_usefulness_rank_ordering(session, patch_session):
    """
    The pillar with the highest |correlation| should get usefulness_rank=1.

    Strategy: make llm_confidence perfectly discriminate (high on hit, low on miss),
    while other pillars are constant (zero variance -> None correlation).
    Constant pillars get rank=None; llm gets rank=1.
    """
    for _ in range(8):
        session.add(_make_prediction(
            llm_confidence=95.0,
            quant_confidence=0.5,
            ml_confidence=0.5,
            venn_abers_confidence=0.5,
            signal_agreement=0.5,
            confidence_pct=80,
            hit_direction_30d=True,
        ))
    for _ in range(8):
        session.add(_make_prediction(
            llm_confidence=15.0,
            quant_confidence=0.5,
            ml_confidence=0.5,
            venn_abers_confidence=0.5,
            signal_agreement=0.5,
            confidence_pct=30,
            hit_direction_30d=False,
        ))
    session.commit()

    result = get_pillar_attribution()
    pillars = result["pillars"]

    # llm_confidence should have rank 1 (only pillar with non-None correlation)
    assert pillars["llm_confidence"]["usefulness_rank"] == 1

    # Constant-valued pillars should have None correlation -> None rank
    for p in ["quant_confidence", "ml_confidence", "venn_abers_confidence", "signal_agreement"]:
        assert pillars[p]["correlation_with_hit_30d"] is None
        assert pillars[p]["usefulness_rank"] is None

    # usefulness_ranking list should contain only llm_confidence
    assert result["usefulness_ranking"] == ["llm_confidence"]


# ---------------------------------------------------------------------------
# 5. test_predictive_lift_computation
# ---------------------------------------------------------------------------

def test_predictive_lift_computation(session, patch_session):
    """
    Predictive lift = pillar_correlation - baseline_confidence_correlation.
    Verify the arithmetic for a controlled dataset.
    """
    # Create rows where llm and confidence both discriminate but at different strengths
    for _ in range(10):
        session.add(_make_prediction(
            llm_confidence=85.0,
            confidence_pct=75,
            hit_direction_30d=True,
            quant_confidence=0.8,
            ml_confidence=0.8,
            venn_abers_confidence=0.8,
            signal_agreement=0.8,
        ))
    for _ in range(10):
        session.add(_make_prediction(
            llm_confidence=25.0,
            confidence_pct=35,
            hit_direction_30d=False,
            quant_confidence=0.2,
            ml_confidence=0.2,
            venn_abers_confidence=0.2,
            signal_agreement=0.2,
        ))
    session.commit()

    result = get_pillar_attribution()
    baseline = result["baseline_confidence_correlation"]

    for pillar_name in PILLAR_COLUMNS:
        pillar_data = result["pillars"][pillar_name]
        corr = pillar_data["correlation_with_hit_30d"]
        lift = pillar_data["predictive_lift"]

        if corr is not None and baseline is not None:
            expected_lift = round(corr - baseline, 4)
            assert lift == pytest.approx(expected_lift, abs=1e-4), (
                f"{pillar_name}: lift={lift}, expected={expected_lift}"
            )
        else:
            assert lift is None


# ---------------------------------------------------------------------------
# 6. test_all_null_pillar
# ---------------------------------------------------------------------------

def test_all_null_pillar(session, patch_session):
    """If every row has ml_confidence=None, correlation should be None."""
    for _ in range(6):
        session.add(_make_prediction(
            ml_confidence=None,
            hit_direction_30d=True,
        ))
    for _ in range(4):
        session.add(_make_prediction(
            ml_confidence=None,
            hit_direction_30d=False,
        ))
    session.commit()

    result = get_pillar_attribution()
    ml = result["pillars"]["ml_confidence"]

    assert ml["correlation_with_hit_30d"] is None
    assert ml["predictive_lift"] is None
    assert ml["missing_rate"] == pytest.approx(1.0, abs=1e-4)
    assert ml["sample_size"] == 0
    assert ml["usefulness_rank"] is None


# ---------------------------------------------------------------------------
# 7. test_bucketed_accuracy_for_pillar
# ---------------------------------------------------------------------------

def test_bucketed_accuracy_for_pillar(session, patch_session):
    """
    Verify bucketed accuracy produces bucket labels with range strings
    and count/hit_rate fields for a pillar with varying values.
    """
    # Spread quant_confidence across [0.1, 0.9] with mixed outcomes
    data = [
        (0.1, False), (0.15, False), (0.2, False),
        (0.3, False), (0.35, True),
        (0.5, True),  (0.55, True),
        (0.7, True),  (0.75, True),
        (0.9, True),
    ]
    for qc, hit in data:
        session.add(_make_prediction(
            quant_confidence=qc,
            hit_direction_30d=hit,
            confidence_pct=int(qc * 100),
        ))
    session.commit()

    result = get_pillar_attribution()
    buckets = result["pillars"]["quant_confidence"]["bucketed_accuracy"]

    # Default is 5 buckets
    assert len(buckets) == 5

    # Each bucket has the required keys
    for b in buckets:
        assert "range" in b
        assert "count" in b
        assert "hit_rate" in b
        assert "-" in b["range"], f"Bucket range should be 'lo-hi', got {b['range']}"

    # Total count across buckets should equal the number of rows with hit data
    total_in_buckets = sum(b["count"] for b in buckets)
    assert total_in_buckets == len(data)

    # The lowest bucket (small quant values) should have a lower hit rate
    # than the highest bucket (large quant values)
    low_bucket = buckets[0]
    high_bucket = buckets[-1]
    if low_bucket["hit_rate"] is not None and high_bucket["hit_rate"] is not None:
        assert high_bucket["hit_rate"] >= low_bucket["hit_rate"]
