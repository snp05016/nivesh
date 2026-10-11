"""ML-12: properties of the heuristic confidence blend (static weights, flag off)."""
from typing import Any

import pytest

from services import confidence_fusion
from services.confidence_fusion import _fuse_final_confidence

_GRID = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
_BASE = {"llm_conf": 55, "quant_conf": 0.5, "venn_abers_conf": 0.5, "signal_agreement": 0.5}


@pytest.fixture(autouse=True)
def _static_weights(monkeypatch):
    monkeypatch.delenv("FUSION_DYNAMIC_WEIGHTS_ENABLED", raising=False)
    monkeypatch.setattr(confidence_fusion, "_WEIGHTS_CACHE", None)
    monkeypatch.setattr(confidence_fusion, "_WEIGHTS_CACHE_TIME", 0.0)


def _fuse(**overrides):
    kwargs: dict[str, Any] = dict(_BASE, ml_conf=None, ml_engine_mode="trained_live_calibrated")
    kwargs.update(overrides)
    return _fuse_final_confidence(**kwargs)


@pytest.mark.parametrize("pillar", ["llm_conf", "quant_conf", "venn_abers_conf", "signal_agreement"])
def test_monotone_in_each_non_ml_pillar(pillar):
    scale = 100 if pillar == "llm_conf" else 1
    fused = [_fuse(**{pillar: v * scale}, ml_conf=0.7, final_direction=1, ml_direction=1)[0] for v in _GRID]
    assert fused == sorted(fused)


def test_monotone_in_agreeing_ml_pillar():
    fused = [_fuse(ml_conf=v, final_direction=1, ml_direction=1)[0] for v in _GRID]
    assert fused == sorted(fused)


def test_disagreeing_ml_pillar_never_raises_confidence():
    without_ml, _ = _fuse(ml_conf=None, final_direction=1, ml_direction=None)
    with_ml, breakdown = _fuse(ml_conf=0.9, final_direction=1, ml_direction=-1)
    assert with_ml <= without_ml
    assert breakdown["ml_confidence"] == pytest.approx(0.1)


@pytest.mark.parametrize(("final_direction", "ml_direction"), [(0, 1), (1, 0), (None, 1), (1, None)])
def test_ml_pillar_excluded_without_both_directions(final_direction, ml_direction):
    _, breakdown = _fuse(ml_conf=0.9, final_direction=final_direction, ml_direction=ml_direction)
    assert breakdown["weights"]["ml"] == 0.0
    assert "ml" not in breakdown["pillars_used"]


def test_missing_pillars_are_renormalized_not_dragged_down():
    fused, breakdown = _fuse_final_confidence(
        llm_conf=60, quant_conf=None, venn_abers_conf=None, signal_agreement=None, ml_conf=None,
    )
    assert fused == 60
    assert breakdown["pillars_used"] == ["llm"]
    assert breakdown["weights"]["llm"] == pytest.approx(1.0)


def test_no_inputs_returns_neutral():
    fused, breakdown = _fuse_final_confidence(None, None, None, None, None)
    assert fused == 50
    assert breakdown["no_inputs"] is True


@pytest.mark.parametrize("mode", ["fallback_technical_heuristic", "trained_lightgbm_baseline", "unavailable", None])
def test_unvalidated_ml_modes_carry_no_weight(mode):
    _, breakdown = _fuse(ml_conf=0.9, ml_engine_mode=mode, final_direction=1, ml_direction=1)
    assert breakdown["weights"]["ml"] == 0.0
    assert sum(breakdown["weights"].values()) == pytest.approx(1.0, abs=0.001)


def test_breakdown_labels_the_number_as_uncalibrated():
    _, breakdown = _fuse(ml_conf=0.7, final_direction=1, ml_direction=1)
    assert breakdown["confidence_kind"] == "heuristic_blend_uncalibrated"
    assert breakdown["weights_version"] == "static-v1"
    assert breakdown["dynamic_weights_active"] is False
