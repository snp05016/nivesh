import pytest
import pandas as pd
import yfinance as yf
from unittest.mock import MagicMock
import routers.market as market_router
import services.nse_data_provider as nse_dp
import database

# Mock yfinance Ticker for all tests
class MockTicker:
    def __init__(self, ticker):
        self.ticker = ticker
        self.info = {
            "longName": "Mock Reliance Industries",
            "currentPrice": 2500.0,
            "regularMarketPrice": 2500.0,
            "previousClose": 2480.0,
            "regularMarketPreviousClose": 2480.0,
            "trailingPE": 25.5,
            "sector": "Energy",
            "heldPercentInsiders": 0.452,
            "heldPercentInstitutions": 0.358,
            "returnOnEquity": 0.15,
            "returnOnCapitalEmployed": 0.18,
            "ebitda": 500000000,
            "totalRevenue": 2000000000,
            "debtToEquity": 0.5,
            "fiftyTwoWeekHigh": 2700.0,
            "fiftyTwoWeekLow": 2100.0,
            "marketCap": 150000000000,
            "longBusinessSummary": "Reliance Industries is an Indian multinational conglomerate."
        }
        self.recommendations = pd.DataFrame(
            [{"Firm": "Mock Firm", "toGrade": "BUY"}],
            index=[pd.Timestamp("2026-06-25")]
        )

    def history(self, *args, **kwargs):
        return pd.DataFrame(
            [[2400.0, 2450.0, 2380.0, 2420.0, 100000]],
            index=[pd.Timestamp("2026-06-25")],
            columns=["Open", "High", "Low", "Close", "Volume"]
        )

    @property
    def quarterly_financials(self):
        return pd.DataFrame(
            [[3500.0 * 1e7, 3600.0 * 1e7], [500.0 * 1e7, 600.0 * 1e7]],
            index=["Total Revenue", "Net Income"],
            columns=[pd.Timestamp("2026-03-31"), pd.Timestamp("2025-12-31")]
        )

    @property
    def dividends(self):
        return pd.Series([10.0, 15.0], index=[pd.Timestamp("2025-06-25"), pd.Timestamp("2026-06-25")])

    @property
    def fast_info(self):
        class FastInfo:
            last_price = 2500.0
        return FastInfo()

    @property
    def calendar(self):
        return {"Dividend Date": [pd.Timestamp("2026-07-25")]}


@pytest.fixture(autouse=True)
def setup_mocks(monkeypatch):
    monkeypatch.setattr(yf, "Ticker", MockTicker)
    monkeypatch.setattr(market_router, "_yf_fetch_info", lambda ticker: MockTicker(ticker).info)
    monkeypatch.setattr(market_router, "_get_quarterly_fin", lambda ticker: (
        MockTicker(ticker), MockTicker(ticker).quarterly_financials
    ))
    monkeypatch.setattr(market_router, "get_price_history", lambda *args, **kwargs: pd.DataFrame(
        [[2400.0, 2450.0, 2380.0, 2420.0, 100000]],
        index=[pd.Timestamp("2026-06-25")],
        columns=["Open", "High", "Low", "Close", "Volume"]
    ))


def test_stock_profile_endpoint_comprehensive(client):
    """Test /api/v1/stock-profile for schema matching and Indian scaling."""
    resp = client.get("/api/v1/stock-profile?ticker=RELIANCE&exchange=NSE")
    assert resp.status_code == 200
    data = resp.json()

    # Schema checks (matching iOS struct)
    assert data["ticker"] == "RELIANCE"
    assert data["exchange"] == "NSE"
    assert data["company_name"] == "Mock Reliance Industries"
    assert data["current_price"] == 2500.0
    assert data["day_change_pct"] == 0.81  # ((2500 - 2480) / 2480) * 100
    assert data["pe_ratio"] == 25.5
    assert data["sector"] == "Energy"
    assert data["promoter_holding_pct"] == 45.2
    assert data["fii_holding_pct"] == 35.8
    assert data["roe_pct"] == 15.0
    assert data["roce_pct"] == 18.0
    assert data["debt_to_equity"] == 0.5
    assert data["week_52_high"] == 2700.0
    assert data["week_52_low"] == 2100.0
    assert data["market_cap_crores"] == 15000.0  # 1.5e11 / 1e7
    assert data["description"] == "Reliance Industries is an Indian multinational conglomerate."
    assert "price_history" in data
    assert "quarterly_financials" in data
    assert isinstance(data["errors"], list)

    # Indian scaling checks for quarterly financials (scaled to crores)
    q_fin = data["quarterly_financials"]
    assert len(q_fin["quarters"]) > 0
    for q in q_fin["quarters"]:
        assert q["revenue"] in (3500.0, 3600.0)
        assert q["net_profit"] in (500.0, 600.0)


def test_quick_info_endpoint(client):
    resp = client.get("/quick-info?ticker=RELIANCE&exchange=NSE")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "RELIANCE"
    assert data["market_cap_crores"] == 15000.0


def test_stock_history_endpoint(client):
    resp = client.get("/api/v1/market/stock-history?ticker=RELIANCE&exchange=NSE&period=1y")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "RELIANCE"
    assert "prices" in data
    assert len(data["prices"]) > 0


def test_quarterly_financials_endpoint(client):
    resp = client.get("/quarterly-financials?ticker=RELIANCE&exchange=NSE")
    assert resp.status_code == 200
    data = resp.json()
    assert "quarters" in data
    assert len(data["quarters"]) > 0
    assert data["quarters"][0]["revenue"] in (3500.0, 3600.0)


def test_analyst_ratings_endpoint(client):
    resp = client.get("/analyst-ratings?ticker=RELIANCE&exchange=NSE")
    assert resp.status_code == 200
    data = resp.json()
    assert "ratings" in data
    assert "consensus" in data


def test_dividends_endpoint(client):
    resp = client.get("/dividends/RELIANCE?exchange=NSE")
    assert resp.status_code == 200


def test_sentiment_trend_endpoint(client):
    resp = client.get("/market/sentiment-trend/RELIANCE?days=30")
    assert resp.status_code == 200


def test_piotroski_endpoint(client):
    resp = client.get("/fundamentals/piotroski/RELIANCE")
    assert resp.status_code == 200
    data = resp.json()
    assert "score" in data


def test_macro_context_endpoint(client):
    resp = client.get("/macro-context/RELIANCE?exchange=NSE")
    assert resp.status_code == 200


def test_analyze_job_spawning_and_polling_idor(client, auth_headers, test_user_id, monkeypatch):
    """Test job polling and ensure IDOR protection blocks unauthorized users."""
    import uuid
    job_id = str(uuid.uuid4())[:12]

    # Insert a job belonging to test_user_id into SQLite test DB
    with database.get_session() as session:
        from models.db_models import AnalysisJob
        from datetime import datetime, timezone
        job = AnalysisJob(
            job_id=job_id,
            user_id=test_user_id,
            ticker="RELIANCE",
            exchange="NSE",
            scan_type="standard",
            status="QUEUED",
            created_at=datetime.now(timezone.utc)
        )
        session.add(job)
        session.commit()

    # 1. Access without query parameter user_id and without Auth header -> 403 Forbidden
    resp = client.get(f"/analyze/job/{job_id}")
    assert resp.status_code == 403
    assert resp.json()["error"] == "job does not belong to this user"

    # 2. Access with incorrect user_id query parameter (e.g. 99999) -> 403 Forbidden
    resp = client.get(f"/analyze/job/{job_id}?user_id=99999")
    assert resp.status_code == 403

    # 3. Access with correct user_id query parameter -> 200 OK
    resp = client.get(f"/analyze/job/{job_id}?user_id={test_user_id}")
    assert resp.status_code == 200
    assert resp.json()["job_id"] == job_id

    # 4. Access with correct Auth header, omitting user_id query parameter -> 200 OK
    resp = client.get(f"/analyze/job/{job_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["job_id"] == job_id

    # 5. Access with mismatched Auth header (using a dummy token representing another user) -> 403
    mismatched_token = database.create_access_token(user_id=99999)
    resp = client.get(f"/analyze/job/{job_id}", headers={"Authorization": f"Bearer {mismatched_token}"})
    assert resp.status_code == 403


def test_analyze_active_endpoint(client, auth_headers):
    resp = client.get("/analyze/active", headers=auth_headers)
    assert resp.status_code == 200


def test_analyze_cancel_endpoint(client, auth_headers):
    resp = client.post("/analyze/non-existent-job-id/cancel", headers=auth_headers)
    # Should either be 404 not found or 200 with error, but should not 500
    assert resp.status_code in (200, 404)


def test_ideas_advisors_endpoint(client):
    resp = client.get("/api/v1/ideas/advisors")
    assert resp.status_code == 200
    data = resp.json()
    assert "advisors" in data


def test_ideas_feed_endpoint(client):
    resp = client.get("/api/v1/ideas/feed")
    assert resp.status_code == 200
    data = resp.json()
    assert "insights" in data


def test_brainstorm_endpoint(client, monkeypatch):
    # Mock LLM generation in brainstorming service
    import services.brainstorming as bs
    monkeypatch.setattr(bs, "generate_brainstorming_ideas", lambda *args, **kwargs: {
        "theme": "Growth",
        "ideas": [
            {
                "title": "Mock Idea 1",
                "description": "High promoter stake, market cap of 15.0 Lakh Crores.",
                "ticker": "RELIANCE"
            }
        ]
    })
    resp = client.post("/brainstorm", json={"topic": "growth", "risk_tolerance": "moderate"})
    assert resp.status_code == 200
    data = resp.json()
    assert "ideas" in data
    # Western scale check (Lakh/Crore instead of Millions/Billions)
    assert "Million" not in str(data) and "Billion" not in str(data)


def test_home_feed_endpoint(client, auth_headers):
    resp = client.get("/api/v1/home-feed?user_id=1", headers=auth_headers)
    assert resp.status_code == 200


def test_morning_summary_endpoint(client, auth_headers, test_user_id, monkeypatch):
    """Test morning summary endpoint and ensure it uses Auth header correctly."""
    # 1. Another user's id -> 403 Forbidden (ARCH-02)
    resp = client.get("/morning-summary/99999", headers=auth_headers)
    assert resp.status_code == 403

    # Mock Anthropic client response
    import anthropic
    mock_anthropic = MagicMock()
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text='{"summary": "• Market is positive.\\n• Watch RELIANCE today.", "movers": ["RELIANCE"], "mood": "positive"}')]
    mock_msg.usage = MagicMock(input_tokens=100, output_tokens=50)
    mock_anthropic.messages.create.return_value = mock_msg
    monkeypatch.setattr(anthropic, "Anthropic", lambda *args, **kwargs: mock_anthropic)
    # The AI brief needs the opt-in 'ai_processing' consent (FINSEC-04).
    monkeypatch.setattr("routers.portfolio.has_active_consent", lambda *_args, **_kwargs: True)

    # 2. Authenticated access -> 200 OK
    resp = client.get(f"/morning-summary/{test_user_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "movers" in data
    assert data["mood"] == "positive"


def test_harvester_endpoints_auth(client, auth_headers):
    # Harvester sources requires auth like its siblings (AUTH-26)
    resp = client.get("/harvester/sources")
    assert resp.status_code == 401
    resp = client.get("/harvester/sources", headers=auth_headers)
    assert resp.status_code == 200

    # Harvester feed requires auth
    resp = client.get("/harvester/feed")
    assert resp.status_code == 401

    resp = client.get("/harvester/feed", headers=auth_headers)
    assert resp.status_code == 200

    # Harvester governance requires auth
    resp = client.get("/harvester/governance/RELIANCE")
    assert resp.status_code == 401

    resp = client.get("/harvester/governance/RELIANCE", headers=auth_headers)
    assert resp.status_code == 200
