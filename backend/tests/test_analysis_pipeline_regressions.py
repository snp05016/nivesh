import json
import sqlite3
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database
from database import AnalysisHistory
from main import app


client = TestClient(app)


def test_init_db_migrates_legacy_analysis_history_columns(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            ticker VARCHAR(30) NOT NULL,
            analysis_date VARCHAR(20) NOT NULL,
            signal VARCHAR(20) NOT NULL,
            confidence_pct FLOAT,
            target_short FLOAT,
            target_medium FLOAT,
            target_long FLOAT,
            full_json TEXT NOT NULL,
            created_at DATETIME
        )
        """
    )
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "ENGINE", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, autoflush=False, autocommit=False))

    database.init_db()

    conn = sqlite3.connect(db_path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(analysis_history)").fetchall()}
    conn.close()

    assert {
        "scan_type",
        "raw_output",
        "promoter_pledged_pct",
        "promoter_pledged_trend",
        "outcome_delta_pct",
        "was_correct",
        "outcome_checked_at",
        "market_regime",
        "calibrated_confidence",
        "conformal_target_upper_3m",
        "conformal_target_lower_3m",
        "quantitative_drivers",
        "tail_risk_flags",
        "confidence_math_breakdown",
    }.issubset(columns)


def test_extreme_request_does_not_return_standard_cache(monkeypatch):
    uid = 992101
    ticker = "PIPEFIX"
    with database.get_session() as session:
        session.query(AnalysisHistory).filter(AnalysisHistory.ticker == ticker).delete()
        session.query(database.AnalysisJob).filter(database.AnalysisJob.user_id == uid).delete()
        session.add(
            AnalysisHistory(
                user_id=uid,
                ticker=ticker,
                analysis_date="2026-06-15",
                signal="HOLD",
                confidence_pct=50,
                full_json=json.dumps(
                    {
                        "ticker": ticker,
                        "exchange": "NSE",
                        "company_name": ticker,
                        "analysis_date": "2026-06-15",
                        "signal": "HOLD",
                        "confidence_pct": 50,
                        "scan_type": "standard",
                    }
                ),
                scan_type="standard",
            )
        )
        session.commit()

    spawned = {}

    def _capture_spawn(*args):
        spawned["args"] = args

    monkeypatch.setattr("services.job_manager.spawn_job", _capture_spawn)

    response = client.post(
        "/analyze",
        json={"ticker": ticker, "exchange": "NSE", "user_id": uid, "scan_type": "extreme"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "QUEUED"
    assert body["scan_type"] == "extreme"
    assert spawned["args"][5] == "extreme"


def test_quant_payload_is_passed_to_reformatter(monkeypatch):
    tools_mod = types.ModuleType("langchain_core.tools")
    tools_mod.tool = lambda fn=None, **kwargs: fn if fn is not None else (lambda wrapped: wrapped)
    monkeypatch.setitem(sys.modules, "langchain_core.tools", tools_mod)
    monkeypatch.setitem(sys.modules, "langchain_community", MagicMock())
    monkeypatch.setitem(sys.modules, "langchain_community.vectorstores", MagicMock())
    monkeypatch.setitem(sys.modules, "langchain_openai", MagicMock())
    import services.orchestrator as orchestrator

    quant_payload = {
        "market_regime": "High Volatility / Crisis",
        "calibrated_confidence": 0.33,
        "conformal_target_upper_3m": 120.0,
        "conformal_target_lower_3m": 80.0,
        "quantitative_drivers": {"Promoter Pledge Risk": -0.2},
        "tail_risk_flags": {"high_pledge_danger": True},
        "confidence_math_breakdown": {
            "base_probability": 0.5,
            "net_shap_adjustment": -0.2,
            "regime_multiplier": 0.55,
            "tail_risk_deduction": 0.3,
            "final_calibrated_confidence": 0.33,
        },
    }
    captured = {}

    class _FakeQuantEngine:
        def __init__(self, ticker):
            self.ticker = ticker

        async def run_full_pipeline(self):
            return quant_payload

    monkeypatch.setattr(orchestrator, "get_analysis_for_date", lambda *args, **kwargs: None)
    monkeypatch.setattr(orchestrator, "get_last_analysis_any_type", lambda *args, **kwargs: None)
    monkeypatch.setattr(orchestrator, "get_all_ticker_history", lambda *args, **kwargs: [])
    monkeypatch.setattr(orchestrator, "run_trading_agents", lambda *args, **kwargs: ("RAW", [], {}))
    monkeypatch.setattr(orchestrator, "_inject_piotroski", lambda *args, **kwargs: None)
    monkeypatch.setattr(orchestrator, "_inject_live_data", lambda result, ticker: result)
    monkeypatch.setattr(orchestrator, "_yf_fetch_info", lambda *args, **kwargs: {})
    monkeypatch.setattr(orchestrator.yf, "Ticker", lambda *args, **kwargs: type("T", (), {"major_holders": ""})())

    def _fake_reformat(raw_output, full_ticker, exchange, prior_analyses=None, scan_type="standard"):
        captured["raw_output"] = raw_output
        return {
            "ticker": full_ticker,
            "exchange": exchange,
            "company_name": full_ticker,
            "analysis_date": "2026-06-15",
            "signal": "HOLD",
            "confidence_pct": 50,
        }

    monkeypatch.setattr(orchestrator, "reformat_with_deepseek", _fake_reformat)
    monkeypatch.setattr("services.quant_engine.QuantitativeEngine", _FakeQuantEngine)

    result = orchestrator.analyze("PIPEQ", "NSE", user_id=992102, scan_type="standard")

    assert "QUANTITATIVE ENGINE OUTPUT (AUTHORITATIVE)" in captured["raw_output"]
    assert "High Volatility / Crisis" in captured["raw_output"]
    assert result["calibrated_confidence"] == 0.33
    assert result["confidence_math_breakdown"]["final_calibrated_confidence"] == 0.33


def test_save_analysis_persists_confidence_math_breakdown():
    ticker = "PIPEMATH"
    payload = {
        "ticker": ticker,
        "exchange": "NSE",
        "company_name": ticker,
        "analysis_date": "2026-06-15",
        "signal": "HOLD",
        "confidence_pct": 50,
        "target_prices": {},
        "fundamentals_snapshot": {},
        "confidence_math_breakdown": {
            "base_probability": 0.5,
            "net_shap_adjustment": 0.1,
            "regime_multiplier": 0.85,
            "tail_risk_deduction": 0.0,
            "final_calibrated_confidence": 0.51,
        },
    }

    with database.get_session() as session:
        session.query(AnalysisHistory).filter(AnalysisHistory.ticker == ticker).delete()
        saved = database.save_analysis(session, None, ticker, payload)
        row = (
            session.query(AnalysisHistory)
            .filter(AnalysisHistory.ticker == ticker)
            .order_by(AnalysisHistory.created_at.desc())
            .first()
        )

    assert saved["confidence_math_breakdown"]["net_shap_adjustment"] == 0.1
    assert row.confidence_math_breakdown["final_calibrated_confidence"] == 0.51


def test_ios_deep_scan_job_request_carries_deep_scan_flag():
    root = Path(__file__).resolve().parents[2]
    network = (root / "ios/StockApp/stockme/stockme/NetworkManager.swift").read_text()
    models = (root / "ios/StockApp/stockme/stockme/Models.swift").read_text()
    screen = (root / "ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift").read_text()

    assert "struct StartJobRequest" in models
    assert "let deepScan: Bool" in models
    assert 'case deepScan = "deep_scan"' in models
    assert "deepScan: deepScan" in network
    assert "scanType: \"deep\"" in screen
