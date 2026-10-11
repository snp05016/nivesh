"""ML-04: dynamic fusion weights need matured outcomes, a significant correlation and a manual opt-in."""
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models.db_models import AnalysisPrediction, Base  # pyright: ignore[reportMissingImports]
from services import confidence_fusion

_FLAG = "FUSION_DYNAMIC_WEIGHTS_ENABLED"


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.delenv(_FLAG, raising=False)
    monkeypatch.setattr(confidence_fusion, "_WEIGHTS_CACHE", None)
    monkeypatch.setattr(confidence_fusion, "_WEIGHTS_CACHE_TIME", 0.0)


@pytest.fixture
def calib_session():
    """In-memory DB behind prediction_calibration_service.get_session."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    @contextmanager
    def _get_session():
        session = Session()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    with patch("services.prediction_calibration_service.get_session", _get_session):
        yield _get_session
    engine.dispose()


def _seed(get_session, n=150, matured=True, llm_predicts_hit=False):
    """n rows, every pillar filled. Non-LLM pillars (and the LLM unless llm_predicts_hit)
    follow a pattern whose mean is equal for hits and misses, i.e. zero correlation."""
    with get_session() as session:
        for i in range(n):
            hit = i % 2 == 0
            flat = 0.4 if (i // 2) % 2 == 0 else 0.6
            llm = (80.0 if hit else 30.0) if llm_predicts_hit else flat * 100
            session.add(AnalysisPrediction(
                symbol=f"GATE{i}.NS",
                recommendation="BULLISH",
                confidence_pct=int(llm),
                llm_confidence=llm,
                quant_confidence=flat,
                venn_abers_confidence=flat,
                signal_agreement=flat,
                ml_confidence=flat,
                hit_direction_30d=hit if matured else None,
            ))


def test_unmatured_rows_are_not_confident(calib_session):
    from services.prediction_calibration_service import get_fusion_weight_recommendations

    _seed(calib_session, matured=False)
    rec = get_fusion_weight_recommendations(min_sample=100)

    assert rec["is_confident"] is False
    assert rec["apply_recommendation"] is False
    assert rec["matured_sample"] == 0
    assert rec["recommended_weights"]["llm_confidence"] == 0.45
    assert rec["recommended_weights"]["ml_confidence"] == 0.05


def test_uninformative_pillars_are_not_confident(calib_session):
    from services.prediction_calibration_service import get_fusion_weight_recommendations

    _seed(calib_session)
    rec = get_fusion_weight_recommendations(min_sample=100)

    assert rec["matured_sample"] == 150
    assert rec["is_confident"] is False
    assert rec["weights_version"] == "static-v1"


def test_predictive_pillar_is_confident_but_applied_only_with_flag(calib_session, monkeypatch):
    from services.prediction_calibration_service import get_fusion_weight_recommendations

    _seed(calib_session, llm_predicts_hit=True)
    rec = get_fusion_weight_recommendations(min_sample=100)

    assert rec["is_confident"] is True
    assert rec["apply_recommendation"] is False
    assert rec["recommended_weights"]["llm_confidence"] == pytest.approx(1.0)
    assert rec["recommended_weights"]["ml_confidence"] == 0.0
    assert rec["weights_version"].startswith("dyn-")

    monkeypatch.setenv(_FLAG, "true")
    assert get_fusion_weight_recommendations(min_sample=100)["apply_recommendation"] is True


def test_flag_off_never_reads_recommendations(monkeypatch):
    import services.prediction_calibration_service as pcs

    def _boom(*_a, **_k):
        raise AssertionError("dynamic weights must not be fetched with the flag off")

    monkeypatch.setattr(pcs, "get_fusion_weight_recommendations", _boom)
    fused, breakdown = confidence_fusion._fuse_final_confidence(70, 0.6, 0.5, 0.5, None)

    assert breakdown["dynamic_weights_active"] is False
    assert breakdown["weights_version"] == "static-v1"
    assert 0 <= fused <= 100


def test_dynamic_weights_never_give_unavailable_ml_weight(monkeypatch):
    import services.prediction_calibration_service as pcs

    monkeypatch.setenv(_FLAG, "1")
    monkeypatch.setattr(pcs, "get_fusion_weight_recommendations", lambda min_sample=100: {
        "is_confident": True,
        "apply_recommendation": True,
        "weights_version": "dyn-test",
        "recommended_weights": {
            "llm_confidence": 0.2, "quant_confidence": 0.2, "venn_abers_confidence": 0.2,
            "signal_agreement": 0.2, "ml_confidence": 0.2,
        },
    })
    _, breakdown = confidence_fusion._fuse_final_confidence(
        40, 0.5, 0.5, 0.5, 0.9, ml_engine_mode="unavailable", final_direction=1, ml_direction=1,
    )

    assert breakdown["dynamic_weights_active"] is True
    assert breakdown["weights_version"] == "dyn-test"
    assert breakdown["weights"]["ml"] == 0.0
    assert sum(breakdown["weights"].values()) == pytest.approx(1.0, abs=0.001)


def test_unapproved_recommendation_is_not_applied(monkeypatch):
    import services.prediction_calibration_service as pcs

    monkeypatch.setenv(_FLAG, "true")
    monkeypatch.setattr(pcs, "get_fusion_weight_recommendations", lambda min_sample=100: {
        "is_confident": True, "apply_recommendation": False, "recommended_weights": {"llm_confidence": 1.0},
    })
    assert confidence_fusion._get_dynamic_weights() is None
