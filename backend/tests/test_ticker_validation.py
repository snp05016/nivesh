"""LLM-21: LLM-emitted tickers are checked against the instrument universe, and a
Western-scale sentence in brainstorm output drops that idea instead of a 500."""
import json
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base, StockUniverse
from services import brainstorming, instrument_universe, llm_budget
from services.youtube_summary import providers
from services.yfinance_client import NSE_TICKERS


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


@pytest.fixture
def universe(monkeypatch):
    """The DB-backed lookup pinned to RELIANCE and TCS; the LLM budget gate opened."""
    monkeypatch.setattr(instrument_universe, "_universe", lambda session=None: {"RELIANCE", "TCS"})
    monkeypatch.setattr(llm_budget, "guard", lambda *_a: None)


def test_validate_tickers_against_stock_universe(session):
    session.add_all([StockUniverse(ticker="RELIANCE.NS"), StockUniverse(ticker="TCS")])
    session.commit()

    valid, invalid = instrument_universe.validate_tickers(
        ["reliance.ns", "HDFC", "AAPL", "TCS", "RELIANCE", " "], session=session)

    assert valid == ["RELIANCE", "TCS"]
    assert invalid == ["HDFC", "AAPL"]


def test_empty_universe_falls_back_to_static_nse_list(session):
    known = next(iter(NSE_TICKERS))
    assert instrument_universe.validate_tickers([known, "AAPL"], session=session) == ([known], ["AAPL"])


def test_brainstorm_nulls_unknown_tickers(client, auth_headers, universe, monkeypatch):
    ideas = [
        {"title": "Energy", "description": "Refining margins.", "ticker": "RELIANCE.NS"},
        {"title": "US tech", "description": "Not listed here.", "ticker": "AAPL"},
    ]
    monkeypatch.setattr(brainstorming, "_deepseek_chat", MagicMock(return_value=json.dumps({"ideas": ideas})))

    resp = client.post("/brainstorm", json={"topic": "energy", "risk_tolerance": "Moderate"}, headers=auth_headers)

    assert resp.status_code == 200
    assert [i["ticker"] for i in resp.json()["ideas"]] == ["RELIANCE", None]


def test_brainstorm_drops_western_scale_idea(client, auth_headers, universe, monkeypatch):
    ideas = [
        {"title": "Banks", "description": "A $2 billion market.", "ticker": "TCS"},
        {"title": "IT", "description": "Rupee earnings of 500 Crores.", "ticker": "TCS"},
    ]
    monkeypatch.setattr(brainstorming, "_deepseek_chat", MagicMock(return_value=json.dumps({"ideas": ideas})))

    resp = client.post("/brainstorm", json={"topic": "it", "risk_tolerance": "Moderate"}, headers=auth_headers)

    assert resp.status_code == 200
    assert [i["title"] for i in resp.json()["ideas"]] == ["IT"]


def test_brainstorm_all_ideas_invalid_is_502_not_500(client, auth_headers, universe, monkeypatch):
    ideas = [{"title": "Banks", "description": "A 2 billion dollar market.", "ticker": "TCS"}]
    monkeypatch.setattr(brainstorming, "_deepseek_chat", MagicMock(return_value=json.dumps({"ideas": ideas})))

    resp = client.post("/brainstorm", json={"topic": "banks", "risk_tolerance": "Moderate"}, headers=auth_headers)

    assert resp.status_code == 502


def test_youtube_sanitize_drops_unknown_tickers(universe):
    out = providers._sanitize({"tickers_mentioned": ["TCS.NS", "HDFC", "AAPL", "TCS"]})
    assert out["tickers_mentioned"] == ["TCS"]
