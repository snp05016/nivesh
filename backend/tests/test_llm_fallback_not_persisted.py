"""LLM-08: an LLM failure is never stored or served as a real result.

- reformat_with_claude's last-resort HOLD dict is flagged is_fallback (and no longer
  carries the internal raw_output); analyze() fails the job on it instead of fusing a
  confidence, saving AnalysisHistory and logging an AnalysisPrediction.
- NL screener: an unparseable LLM reply is a 422 and a DB failure a 503; neither is cached.
The YouTube summary path (empty summary -> 502, never cached) is covered by
tests/feature_tests/harvesters/test_youtube_summary.py (GH-634).
"""
import sys
import types
import uuid
from unittest.mock import MagicMock, patch

import pytest

TICKER = "LLMFALL"
NL_URL = "/api/v1/screener/natural-language"


@pytest.fixture
def orch(monkeypatch):
    """services.orchestrator imported with its optional LangChain deps stubbed."""
    tools_mod = types.ModuleType("langchain_core.tools")
    setattr(tools_mod, "tool", lambda fn=None, **kwargs: fn if fn is not None else (lambda wrapped: wrapped))
    monkeypatch.setitem(sys.modules, "langchain_core.tools", tools_mod)
    monkeypatch.setitem(sys.modules, "langchain_community", MagicMock())
    monkeypatch.setitem(sys.modules, "langchain_community.vectorstores", MagicMock())
    monkeypatch.setitem(sys.modules, "langchain_openai", MagicMock())
    import services.orchestrator as orchestrator
    return orchestrator


def test_ultimate_fallback_is_flagged_without_raw_output(orch, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    result = orch.reformat_with_claude("INTERNAL PIPELINE TEXT", f"{TICKER}.NS", "NSE")

    assert result["is_fallback"] is True
    assert "raw_output" not in result


def _counts() -> tuple[int, int]:
    import database
    from models.db_models import AnalysisHistory, AnalysisPrediction  # pyright: ignore[reportMissingImports]

    with database.get_session() as s:
        return (
            s.query(AnalysisHistory).filter(AnalysisHistory.ticker == TICKER).count(),
            s.query(AnalysisPrediction).filter(AnalysisPrediction.symbol.like(f"{TICKER}%")).count(),
        )


def test_analyze_fails_on_fallback_and_persists_nothing(orch, monkeypatch):
    class _FailingQuantEngine:
        def __init__(self, ticker):
            raise RuntimeError("quant engine disabled in this test")

    monkeypatch.setattr(orch, "get_analysis_for_date", lambda *args, **kwargs: None)
    monkeypatch.setattr(orch, "get_all_ticker_history", lambda *args, **kwargs: [])
    monkeypatch.setattr(orch, "run_trading_agents", lambda *args, **kwargs: ("RAW", [], {}))
    monkeypatch.setattr(orch, "_run_calibration_pipeline", lambda ticker, fs, raw: raw)
    monkeypatch.setattr(orch, "_yf_fetch_info", lambda *args, **kwargs: {})
    monkeypatch.setattr(orch.yf, "Ticker", lambda *args, **kwargs: type("T", (), {"major_holders": "", "news": []})())
    monkeypatch.setattr("services.quant_engine.QuantitativeEngine", _FailingQuantEngine)
    monkeypatch.setattr(
        orch, "reformat_with_deepseek",
        lambda *args, **kwargs: {"signal": "HOLD", "confidence_pct": 0, "is_fallback": True},
    )
    fuse = MagicMock(side_effect=AssertionError("fallback must not be fused"))
    monkeypatch.setattr(orch, "_fuse_final_confidence", fuse)
    before = _counts()

    with pytest.raises(RuntimeError, match="could not be generated"):
        orch.analyze(TICKER, "NSE", scan_type="standard")

    fuse.assert_not_called()
    assert _counts() == before


@patch("services.nl_screener.cache_set")
@patch("services.nl_screener.deepseek_chat")
def test_nl_screener_garbage_is_422_and_not_cached(mock_chat, mock_cache_set, client):
    mock_chat.return_value = "garbage"

    resp = client.post(NL_URL, json={"query": f"cheap banks {uuid.uuid4().hex}"})

    assert resp.status_code == 422
    assert "results" not in resp.json()
    mock_cache_set.assert_not_called()


@patch("services.nl_screener.cache_set")
@patch("services.nl_screener.deepseek_chat")
def test_nl_screener_db_failure_is_503_and_not_cached(mock_chat, mock_cache_set, client, monkeypatch):
    mock_chat.return_value = '{"parsed_filters": {"pe_max": 20}}'

    def _boom():
        raise RuntimeError("db down")

    monkeypatch.setattr("services.nl_screener.get_session", _boom)

    resp = client.post(NL_URL, json={"query": f"low pe stocks {uuid.uuid4().hex}"})

    assert resp.status_code == 503
    assert "results" not in resp.json()
    mock_cache_set.assert_not_called()
