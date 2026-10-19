"""SILENT-16: analysis-pipeline degradations are explicit, never in-band defaults.

A failed QuantEngine is a missing pillar (not a zeroed AUTHORITATIVE block), missing fusion
pillars are reported instead of imputed, every stage reports ok|degraded|failed, a failed
save fails the job, and the write-only DLQ is gone."""
import ast
import sys
import types
from pathlib import Path

import pytest

from services import confidence_fusion
from services.confidence_fusion import _fuse_final_confidence
from tests.test_calibration_pipeline_unwrap import orchestrator, stub_pipeline  # noqa: F401 (fixtures)

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _static_weights(monkeypatch):
    monkeypatch.delenv("FUSION_DYNAMIC_WEIGHTS_ENABLED", raising=False)
    monkeypatch.setattr(confidence_fusion, "_WEIGHTS_CACHE", None)


def test_fusion_missing_pillars_renormalised():
    fused, breakdown = _fuse_final_confidence(
        llm_conf=80, quant_conf=None, venn_abers_conf=None, signal_agreement=None, ml_conf=None)
    assert fused == 80
    assert breakdown["quant_confidence"] is None
    assert set(breakdown["missing_pillars"]) == {"quant", "venn_abers", "signal_agreement"}
    assert breakdown["degraded"] is True


def test_fusion_all_present_unchanged():
    fused, breakdown = _fuse_final_confidence(
        llm_conf=80, quant_conf=0.7, venn_abers_conf=0.6, signal_agreement=0.5, ml_conf=None)
    # static non-ML weights 0.45/0.25/0.15/0.10 renormalised over 0.95
    assert fused == round((0.45 * 0.8 + 0.25 * 0.7 + 0.15 * 0.6 + 0.10 * 0.5) / 0.95 * 100)
    # ML carries no weight in the default (ungated) mode, so it is not "missing"
    assert breakdown["missing_pillars"] == []
    assert breakdown["degraded"] is False


def test_no_dlq_symbols():
    tree = ast.parse((BACKEND / "services" / "orchestrator.py").read_text())
    names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assigned = {t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    assert not {"enqueue_dlq", "drain_dlq"} & names
    assert not {"_DLQ_PATH", "_DLQ_LOCK"} & assigned


def test_quant_prompt_block(orchestrator):  # noqa: F811
    missing = orchestrator._quant_prompt_block(None)
    assert "UNAVAILABLE" in missing
    assert "AUTHORITATIVE" not in missing
    present = orchestrator._quant_prompt_block({"market_regime": "Bull", "calibrated_confidence": 0.6})
    assert "RULE-BASED QUANT HEURISTICS" in present
    assert "Bull" in present


def test_calibration_task_failure_marks_degraded(orchestrator, stub_pipeline, monkeypatch):  # noqa: F811
    def _boom(symbol):
        raise RuntimeError("nse down")

    monkeypatch.setattr(sys.modules["services.microstructure_engine"], "compute_pcr_gex", _boom)
    final_state: dict = {}
    orchestrator._run_calibration_pipeline("TCS", final_state, "RAW", None)
    assert final_state["_calibration_status"] == "degraded"
    assert final_state["_calibration_failed_tasks"] == ["microstructure"]


def _stub_analyze(orch, monkeypatch, captured):
    monkeypatch.setattr(orch, "get_analysis_for_date", lambda *a, **k: None)
    monkeypatch.setattr(orch, "get_all_ticker_history", lambda *a, **k: [])
    monkeypatch.setattr(orch, "_inject_piotroski", lambda *a, **k: None)
    monkeypatch.setattr(orch, "_inject_live_data", lambda result, ticker: result)
    monkeypatch.setattr(orch, "_yf_fetch_info", lambda *a, **k: {})
    monkeypatch.setattr(orch.yf, "Ticker", lambda *a, **k: types.SimpleNamespace(major_holders=""))
    monkeypatch.setattr(orch, "run_trading_agents", lambda *a, **k: ("RAW", [], {}))
    monkeypatch.setattr(orch, "_run_calibration_pipeline", lambda ticker, fs, raw, *_a: raw)
    monkeypatch.setattr(orch, "_log_prediction", lambda *a, **k: None)

    def _reformat(raw_output, *a, **k):
        captured["raw_output"] = raw_output
        return {"signal": "HOLD", "confidence_pct": 60}

    monkeypatch.setattr(orch, "reformat_with_deepseek", _reformat)

    class _FailingQuantEngine:
        def __init__(self, ticker):
            raise RuntimeError("quant engine down")

    quant_mod = types.ModuleType("services.quant_engine")
    setattr(quant_mod, "QuantitativeEngine", _FailingQuantEngine)
    monkeypatch.setitem(sys.modules, "services.quant_engine", quant_mod)


def test_quant_failure_is_a_missing_pillar(orchestrator, monkeypatch):  # noqa: F811
    captured: dict = {}
    _stub_analyze(orchestrator, monkeypatch, captured)
    monkeypatch.setattr(orchestrator, "_save_and_fetch_advisors", lambda result, *a, **k: (result, []))

    result = orchestrator.analyze("DEGRADE", "NSE", user_id=None)

    assert "QUANTITATIVE ENGINE OUTPUT: UNAVAILABLE" in captured["raw_output"]
    assert "Data Unavailable" not in captured["raw_output"]
    assert result.get("market_regime") != "Data Unavailable"
    assert result["confidence_breakdown"]["quant_confidence"] is None
    assert "quant" in result["confidence_breakdown"]["missing_pillars"]
    assert result["pipeline_status"]["quant"] == "failed"
    assert result["degraded"] is True


def test_save_failure_fails_the_job(orchestrator, monkeypatch):  # noqa: F811
    _stub_analyze(orchestrator, monkeypatch, {})

    def _save_fails(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(orchestrator, "_save_and_fetch_advisors", _save_fails)
    with pytest.raises(RuntimeError, match="db down"):
        orchestrator.analyze("DEGRADE", "NSE", user_id=None)


def test_cache_hit_keeps_missing_quant_missing(orchestrator, monkeypatch):  # noqa: F811
    """A report saved after a QuantEngine failure has no quant keys; a later cache hit must not
    rebuild them as calibrated_confidence=0.0 / market_regime='Unknown'."""
    from contextlib import contextmanager
    from unittest.mock import MagicMock

    @contextmanager
    def _session():
        yield MagicMock()

    # get_analysis_for_date always setdefaults confidence_math_breakdown={} on cached rows.
    cached = {"signal": "HOLD", "confidence_pct": 60, "company_name": "Degrade Ltd",
              "confidence_math_breakdown": {}}
    monkeypatch.setattr(orchestrator, "get_session", _session)
    monkeypatch.setattr(orchestrator, "get_analysis_for_date", lambda *a, **k: dict(cached))
    monkeypatch.setattr(orchestrator, "_inject_piotroski", lambda *a, **k: None)
    monkeypatch.setattr(orchestrator, "_inject_live_data", lambda result, ticker: result)

    result = orchestrator.analyze("DEGRADE", "NSE", user_id=None)

    assert result["_cache_type"] == "CACHE HIT"
    assert result.get("calibrated_confidence") is None
    assert "market_regime" not in result
    assert "quantitative_drivers" not in result
    assert "tail_risk_flags" not in result


def test_quant_payload_from_report(orchestrator):  # noqa: F811
    assert orchestrator._quant_payload_from_report({"signal": "HOLD"}) is None
    assert orchestrator._quant_payload_from_report({"confidence_math_breakdown": {}}) is None
    payload = orchestrator._quant_payload_from_report({"market_regime": "Bull", "calibrated_confidence": None})
    assert payload == {"market_regime": "Bull"}
    assert orchestrator._normalize_response({}, quant_payload={"market_regime": "Bull"})["calibrated_confidence"] is None
