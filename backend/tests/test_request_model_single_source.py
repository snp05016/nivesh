"""ARCH-01 regression: request/response models are defined once, in schemas/.

helpers.py kept stale copies that the routers bound. Its PortfolioUpdateRequest had
no target_price/purchase_date and its PortfolioAddRequest no transaction_type/notes,
so PUT /portfolio/update and POST /portfolio(/add) returned 500 on every call (#655),
while the tests exercised the unused schemas/ copies.
"""
import uuid
from unittest.mock import patch

import pytest
from pydantic import ValidationError

import helpers
import schemas

MODEL_NAMES = (
    "LoginRequest", "RegisterRequest", "AnalyzeRequest",
    "WatchlistAddRequest", "WatchlistRemoveRequest",
    "PortfolioAddRequest", "PortfolioRemoveRequest", "PortfolioUpdateRequest", "PortfolioNoteRequest",
    "AlertAddRequest", "AlertRemoveRequest", "BatchAnalyzeRequest",
    "TradeJournalAddRequest", "TradeJournalUpdateRequest",
    "EarningsSyncRatioResponse", "YoYAggregateResponse",
    "InstitutionalLeaderboardResponse", "NetWorthSnapshotResponse",
)


def _register_and_login(client) -> tuple[int, dict[str, str]]:
    username = f"arch01_{uuid.uuid4().hex[:10]}"
    password = "AuditPass!123"
    reg = client.post("/register", json={"username": username, "password": password, "display_name": "ARCH-01"})
    assert reg.status_code == 200, reg.text
    login = client.post("/login", json={"username": username, "password": password})
    assert login.status_code == 200, login.text
    data = login.json()
    return data["user_id"], {"Authorization": f"Bearer {data['access_token']}"}


def test_helpers_models_are_the_schemas_classes():
    for name in MODEL_NAMES:
        assert getattr(helpers, name) is getattr(schemas, name), name


@pytest.mark.parametrize("path", ["/portfolio", "/portfolio/add"])
def test_add_holding_with_ios_payload_returns_200(client, path):
    user_id, headers = _register_and_login(client)
    payload = {  # NetworkManager.addHolding body, field for field
        "user_id": user_id, "ticker": "BAJAJ-AUTO", "exchange": "NSE",
        "company_name": "Bajaj Auto Ltd", "shares": 10.0, "buy_price": 8000.0,
        "group_name": "holdings", "purchase_date": "11-Oct-2026", "notes": "",
        "target_price": 0.0, "transaction_type": "BUY",
    }
    with patch("routers.portfolio._yf_price", return_value=(8100.0, 8050.0)):
        resp = client.post(path, json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["ticker"] == "BAJAJ-AUTO"
    assert resp.json()["shares"] == 10.0


def test_update_holding_with_ios_payload_persists(client):
    user_id, headers = _register_and_login(client)
    with patch("routers.portfolio._yf_price", return_value=(1550.0, 1540.0)):
        added = client.post("/portfolio/add", json={
            "user_id": user_id, "ticker": "INFY", "company_name": "Infosys Ltd",
            "shares": 10.0, "buy_price": 1500.0,
        }, headers=headers)
        assert added.status_code == 200, added.text
        # NetworkManager.updateHolding body: no target_price / purchase_date
        updated = client.put("/portfolio/update", json={
            "user_id": user_id, "ticker": "INFY", "shares": 12.0, "buy_price": 1500.0,
        }, headers=headers)
    assert updated.status_code == 200, updated.text
    assert updated.json()["shares"] == 12.0

    with patch("routers.portfolio._yf_price_with_status", return_value=(1550.0, 1540.0, "live", None)):
        listed = client.get(f"/portfolio/{user_id}", headers=headers)
    assert listed.status_code == 200, listed.text
    row = next(h for h in listed.json()["holdings"] if h["ticker"] == "INFY")
    assert row["shares"] == 12.0


def test_schemas_keep_fields_only_the_helpers_copies_had():
    req = schemas.AnalyzeRequest(ticker=" bajaj-auto ", language="hi", debate_rounds=2, risk_tolerance="moderate")
    assert req.ticker == "BAJAJ-AUTO"
    assert (req.language, req.debate_rounds, req.risk_tolerance) == ("hi", 2, "moderate")
    assert schemas.AnalyzeRequest(ticker="m&m").ticker == "M&M"
    with pytest.raises(ValidationError):
        schemas.AnalyzeRequest(ticker="RELI ANCE")
    add = schemas.PortfolioAddRequest(user_id=1, ticker="TCS", company_name="TCS", shares=1, buy_price=1, is_virtual=True)
    assert add.is_virtual is True
