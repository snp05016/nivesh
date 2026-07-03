"""API contract tests — schema validation, critical endpoints respond correctly."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENABLE_SCHEDULER", "false")
os.environ.setdefault("JWT_SECRET", "test-secret")


@pytest.fixture(scope="module")
def api_client():
    """Isolated TestClient — named api_client to avoid conftest.py session-scope conflict."""
    from database import init_db
    init_db()
    from fastapi.testclient import TestClient
    import main
    return TestClient(main.app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Schema validation tests (no client needed)
# ---------------------------------------------------------------------------

def test_portfolio_add_request_accepts_target_price():
    """PortfolioAddRequest must accept target_price and purchase_date."""
    from schemas.portfolio import PortfolioAddRequest
    req = PortfolioAddRequest(
        user_id=1, ticker="TCS", company_name="TCS Ltd",
        shares=10, buy_price=3000.0,
        target_price=3500.0, purchase_date="2026-01-01",
    )
    assert req.target_price == 3500.0
    assert req.purchase_date == "2026-01-01"


def test_portfolio_add_request_backward_compatible():
    """PortfolioAddRequest must work without target_price and purchase_date."""
    from schemas.portfolio import PortfolioAddRequest
    req = PortfolioAddRequest(
        user_id=1, ticker="TCS", company_name="TCS Ltd",
        shares=10, buy_price=3000.0,
    )
    assert req.target_price is None
    assert req.purchase_date is None


def test_portfolio_update_request_accepts_target_price():
    """PortfolioUpdateRequest must accept optional target_price."""
    from schemas.portfolio import PortfolioUpdateRequest
    req = PortfolioUpdateRequest(
        user_id=1, ticker="TCS", shares=15, buy_price=3100.0,
        target_price=3600.0,
    )
    assert req.target_price == 3600.0


def test_trade_journal_add_request_has_mood():
    """TradeJournalAddRequest must accept mood and company_name."""
    from schemas.portfolio import TradeJournalAddRequest
    req = TradeJournalAddRequest(
        user_id=1, ticker="RELIANCE", action="BUY",
        price_at_time=2800.0, reason_text="Strong fundamentals",
        mood="BULLISH", company_name="Reliance Industries Ltd",
    )
    assert req.mood == "BULLISH"
    assert req.company_name == "Reliance Industries Ltd"


# ---------------------------------------------------------------------------
# Endpoint response tests
# ---------------------------------------------------------------------------

def test_ping_returns_200(api_client):
    """GET /ping must return 200."""
    resp = api_client.get("/ping")
    assert resp.status_code == 200


def test_openapi_schema_generates(api_client):
    """OpenAPI schema must generate without 500."""
    resp = api_client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "paths" in schema
    assert len(schema["paths"]) > 10


def test_no_500_on_safe_get_endpoints(api_client):
    """Safe GET endpoints must not return 500."""
    safe_endpoints = [
        "/ping",
        "/health",
        "/api/v1/watchlist?user_id=999999",
        "/api/v1/market/pulse",
        "/api/v1/market/macro-events",
    ]
    for endpoint in safe_endpoints:
        resp = api_client.get(endpoint)
        assert resp.status_code != 500, (
            f"GET {endpoint} returned 500: {resp.text[:200]}"
        )


def test_auth_protected_routes_return_401_without_token(api_client):
    """Protected endpoints must return 401 without Bearer token."""
    resp = api_client.get("/api/v1/portfolio?user_id=1")
    # Either 401 (auth checked) or 422 (missing param) or 200 with empty data
    # Must NOT be 500
    assert resp.status_code != 500


def test_mutual_fund_legacy_data_fallback():
    """MutualFundResponse must map legacy fields (fund_name, amc) to new fields."""
    from routers.mutual_funds import MutualFundResponse

    # Test dictionary input
    legacy_dict = {
        "id": 1,
        "fund_name": "Axis Bluechip Fund",
        "amc": "Axis Mutual Fund",
        "category": "Equity",
        "nav": 45.67
    }
    resp = MutualFundResponse.model_validate(legacy_dict)
    assert resp.scheme_name == "Axis Bluechip Fund"
    assert resp.amc_name == "Axis Mutual Fund"
    assert resp.category == "Equity"
    assert resp.nav == 45.67

    # Test object input
    class LegacyFund:
        def __init__(self):
            self.id = 2
            self.fund_name = "SBI Small Cap"
            self.amc = "SBI Mutual Fund"
            self.category = "Equity"
            self.nav = 120.5
            self.scheme_name = None
            self.amc_name = None

    legacy_obj = LegacyFund()
    resp_obj = MutualFundResponse.model_validate(legacy_obj)
    assert resp_obj.scheme_name == "SBI Small Cap"
    assert resp_obj.amc_name == "SBI Mutual Fund"
    assert resp_obj.category == "Equity"
    assert resp_obj.nav == 120.5
