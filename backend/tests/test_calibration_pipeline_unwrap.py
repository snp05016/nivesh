"""ML-V1: the math engines return pydantic models, but _run_calibration_pipeline only unwrapped
dicts, so Venn-Abers, calibration metrics, Rank-IC and currency spillover were always dropped.
Venn-Abers must also be fed the pre-fusion quant confidence (0-1), not the regime multiplier."""
import sys
import types
from unittest.mock import MagicMock

import pytest

from services.math_engines import currency_commodity as cc_mod
from services.math_engines import venn_abers as va_mod
from services.math_engines import calibration_metrics as cm_mod
from services.math_engines import information_coefficient as ic_mod
from services.math_engines.currency_commodity import CurrencyCommodityOutput, CurrencyCommodityResponse
from services.math_engines.venn_abers import VennAbersOutput, VennAbersResponse
from services.math_engines.calibration_metrics import CalibrationResponse
from services.math_engines.information_coefficient import InformationCoefficientResponse


@pytest.fixture
def orchestrator(monkeypatch):
    tools_mod = types.ModuleType("langchain_core.tools")
    setattr(tools_mod, "tool", lambda fn=None, **kwargs: fn if fn is not None else (lambda wrapped: wrapped))
    monkeypatch.setitem(sys.modules, "langchain_core.tools", tools_mod)
    monkeypatch.setitem(sys.modules, "langchain_community", MagicMock())
    monkeypatch.setitem(sys.modules, "langchain_community.vectorstores", MagicMock())
    monkeypatch.setitem(sys.modules, "langchain_openai", MagicMock())
    import services.orchestrator as orch
    return orch


def _module(monkeypatch, name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, name, mod)


def _ok_va():
    return VennAbersResponse(status="ok", output=VennAbersOutput(
        calibrated_confidence=0.62, confidence_interval=[0.55, 0.7], sample_size=40,
        method="isotonic", raw_confidence=0.6))


def _insufficient_va():
    return VennAbersResponse(status="insufficient_data", output=VennAbersOutput(
        calibrated_confidence=0.6, confidence_interval=[0.6, 0.6], sample_size=3,
        method="passthrough", raw_confidence=0.6, min_required=30))


@pytest.fixture
def stub_pipeline(monkeypatch):
    """Stub every dependency imported inside _run_calibration_pipeline; return the VA call log."""
    _module(monkeypatch, "services.factor_engine", compute_indicators=lambda *a, **k: {})
    _module(monkeypatch, "services.confidence_engine",
            compute_signal_agreement=lambda reports: {"agreement_ratio": 0.5},
            compute_conformal_bounds=lambda *a, **k: {},
            find_historical_analogues=lambda *a, **k: {},
            apply_bear_asymmetry=lambda raw: {})
    _module(monkeypatch, "services.microstructure_engine", compute_pcr_gex=lambda s: {})
    _module(monkeypatch, "services.sector_rotation", compute_rrg_quadrant=lambda s: {})
    _module(monkeypatch, "services.filings_extractor", extract_auditor_info=lambda t: {})
    _module(monkeypatch, "services.nse_data_provider",
            get_delivery_data=lambda s: {}, get_price_history=lambda *a, **k: None)
    _module(monkeypatch, "services.qlib_engine.ml_client",
            build_ml_ohlcv_payload=lambda df: [], predict_cross_section_sync=lambda *a, **k: None)

    calls = {"va_inputs": [], "va_response": _ok_va()}

    class FakeVA:
        def compute(self, ticker, data, session=None):
            calls["va_inputs"].append(data["raw_confidence"])
            return calls["va_response"]

    class FakeCurrency:
        def compute(self, ticker, data, session=None):
            return CurrencyCommodityResponse(status="ok", output=CurrencyCommodityOutput(
                modifier=0.01, sector="IT", description="INR weakness tailwind"))

    class FakeCalMetrics:
        def compute(self, ticker, data, session=None):
            return CalibrationResponse(status="error", error="no data")

    class FakeIC:
        def compute(self, ticker, data, session=None):
            return InformationCoefficientResponse(status="error", error="no data")

    monkeypatch.setattr(va_mod, "VennAbersEngine", FakeVA)
    monkeypatch.setattr(cc_mod, "CurrencyCommodityEngine", FakeCurrency)
    monkeypatch.setattr(cm_mod, "CalibrationMetricsEngine", FakeCalMetrics)
    monkeypatch.setattr(ic_mod, "InformationCoefficientEngine", FakeIC)
    return calls


@pytest.mark.parametrize("quant_conf", [0.55, 55.0])
def test_pydantic_engine_outputs_reach_final_state(orchestrator, stub_pipeline, quant_conf):
    final_state: dict = {"sector": "IT"}
    out = orchestrator._run_calibration_pipeline(
        "TCS", final_state, "RAW", {"calibrated_confidence": quant_conf})

    assert stub_pipeline["va_inputs"] == [pytest.approx(0.55)]
    assert final_state["_venn_abers_confidence"] == 0.62
    assert final_state["_confidence_interval"] == [0.55, 0.7]
    assert final_state["_currency_commodity_spillover"]["modifier"] == 0.01
    assert final_state["_currency_commodity_spillover"]["description"] == "INR weakness tailwind"
    assert "VA Calibrated: 0.620" in out
    assert "Macro Spillover: +1.00%" in out
    assert out.endswith("RAW")


def test_insufficient_data_va_is_ignored(orchestrator, stub_pipeline):
    stub_pipeline["va_response"] = _insufficient_va()
    final_state = {}
    orchestrator._run_calibration_pipeline("TCS", final_state, "RAW", {"calibrated_confidence": 0.6})

    assert stub_pipeline["va_inputs"] == [0.6]
    assert "_venn_abers_confidence" not in final_state
    assert "_confidence_interval" not in final_state


@pytest.mark.parametrize("quant_payload", [None, {}, {"calibrated_confidence": None}, {"calibrated_confidence": 0}])
def test_va_skipped_without_quant_confidence(orchestrator, stub_pipeline, quant_payload):
    final_state = {}
    orchestrator._run_calibration_pipeline("TCS", final_state, "RAW", quant_payload)

    assert stub_pipeline["va_inputs"] == []
    assert "_venn_abers_confidence" not in final_state
    # Other engines still flow through.
    assert final_state["_currency_commodity_spillover"]["modifier"] == 0.01


def test_engine_output_accepts_models_and_dicts(orchestrator):
    eo = orchestrator._engine_output
    assert eo(_ok_va())["calibrated_confidence"] == 0.62
    assert eo({"status": "ok", "output": {"modifier": 0.02}}) == {"modifier": 0.02}
    assert eo(None) == {}
    assert eo({}) == {}
    assert eo(_insufficient_va()) == {}
    assert eo(VennAbersResponse(status="error", error="boom")) == {}
    assert eo({"status": "ok", "output": None}) == {}


def test_venn_abers_training_scale_is_normalized():
    """History stores some confidences as percent (e.g. the 40.0 governance cap)."""
    # 0.8 -> correct; 20.0 (= 0.2) -> wrong. Unnormalized, 20.0 sorts above 0.8 and the
    # isotonic fit pools them to ~0.5; normalized, 0.8 calibrates to the 0.95 ceiling.
    rows = [(0.8, True)] * 20 + [(20.0, False)] * 20
    session = MagicMock()
    session.query.return_value.filter.return_value.all.return_value = rows

    res = va_mod.VennAbersEngine().compute("TCS", {"raw_confidence": 0.8}, session=session)

    assert res.status == "ok"
    assert res.output is not None
    assert res.output.calibrated_confidence > 0.9
