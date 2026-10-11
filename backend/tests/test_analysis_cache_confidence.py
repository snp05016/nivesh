"""ML-12: a cache hit returns the confidence fused on first view, without re-fusing or logging."""
from uuid import uuid4


def test_cache_hit_keeps_stored_confidence_and_logs_nothing(monkeypatch):
    import database
    from models.db_models import AnalysisPrediction  # pyright: ignore[reportMissingImports]
    from services import orchestrator

    symbol = f"CACHE{uuid4().hex[:6].upper()}"
    breakdown = {"weights": {"llm": 1.0}, "weights_version": "static-v1"}
    cached = {
        "ticker": symbol,
        "signal": "BULLISH",
        "confidence_pct": 72,
        "confidence_breakdown": breakdown,
        "ml_confidence": 0.85,
        "signal_agreement": 0.8,
    }

    def _no_refusion(*_a, **_k):
        raise AssertionError("cache hits must not re-fuse confidence")

    monkeypatch.setattr(orchestrator, "_resolve_ticker", lambda ticker, exchange: f"{ticker}.NS")
    monkeypatch.setattr(orchestrator, "get_analysis_for_date", lambda *a, **k: dict(cached))
    monkeypatch.setattr(orchestrator, "_normalize_response", lambda result, *a, **k: result)
    monkeypatch.setattr(orchestrator, "_inject_live_data", lambda result, ticker: result)
    monkeypatch.setattr(orchestrator, "_inject_piotroski", lambda *a, **k: None)
    monkeypatch.setattr(orchestrator, "_fuse_final_confidence", _no_refusion)

    result = orchestrator.analyze(symbol, "NSE", user_id=None, scan_type="standard")

    assert result["_cache_type"] == "CACHE HIT"
    assert result["confidence_pct"] == 72
    assert result["confidence_breakdown"] == breakdown
    assert result["confidence_disclosure"] == orchestrator.CONFIDENCE_DISCLOSURE
    with database.get_session() as session:
        logged = session.query(AnalysisPrediction).filter(AnalysisPrediction.symbol == symbol).count()
    assert logged == 0
