"""GH-656: the price-alert list and check routes return the envelopes iOS decodes.

Swift decodes AlertsResponse {"alerts": [...]} and AlertCheckResponse
{"newly_triggered": [...]} (Models/AlertModels.swift). Both routes used to return
a bare list, so the Alerts screen always showed "NO ALERTS SET" and never a
trigger banner; /alerts/check also returned every alert, not the newly crossed ones.
"""
import random

import pytest

import database
from database import create_access_token
from models.db_models import PriceTarget, User
from services import alerts_service

_PRICE_KEYS = {"id", "ticker", "company_name", "target_price", "direction",
               "current_price", "distance_pct", "triggered", "created_at"}


@pytest.fixture
def alert_user():
    """A fresh user with one 'above 100' TCS alert, so other tests' alerts never interfere."""
    uid = random.randint(40_000_000, 49_999_999)
    with database.get_session() as session:
        session.add(User(id=uid, username=f"alerts_{uid}", password_hash="x", display_name="Alerts"))
        session.add(PriceTarget(user_id=uid, ticker="TCS", target_price=100.0,
                                direction="above", triggered=False))
        session.commit()
    yield uid, {"Authorization": f"Bearer {create_access_token(uid)}"}
    with database.get_session() as session:
        session.query(PriceTarget).filter(PriceTarget.user_id == uid).delete()
        session.commit()


@pytest.fixture
def price(monkeypatch):
    """Set the quote every ticker resolves to; never reaches yfinance."""
    quote = {"value": (150.0, 140.0)}
    monkeypatch.setattr(alerts_service, "_to_ns", lambda t: f"{t}.NS")
    monkeypatch.setattr(alerts_service, "_yf_price", lambda _sym: quote["value"])
    return quote


def test_get_alerts_returns_envelope(client, alert_user, price):
    uid, headers = alert_user

    resp = client.get(f"/alerts/{uid}", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, dict) and isinstance(body["alerts"], list)
    assert len(body["alerts"]) == 1
    assert set(body["alerts"][0]) == _PRICE_KEYS
    assert body["alerts"][0]["current_price"] == 150.0


def test_check_returns_newly_triggered_once(client, alert_user, price):
    uid, headers = alert_user

    first = client.get(f"/alerts/check/{uid}", headers=headers)
    assert first.status_code == 200
    triggered = first.json()["newly_triggered"]
    assert len(triggered) == 1
    assert triggered[0]["ticker"] == "TCS"
    assert triggered[0]["current_price"] == 150.0
    assert triggered[0]["target_price"] == 100.0
    assert triggered[0]["direction"] == "above"

    second = client.get(f"/alerts/check/{uid}", headers=headers)
    assert second.json() == {"newly_triggered": []}

    listed = client.get(f"/alerts/{uid}", headers=headers).json()["alerts"]
    assert listed[0]["triggered"] is True


def test_check_skips_unknown_price(client, alert_user, price):
    uid, headers = alert_user
    price["value"] = (None, None)

    resp = client.get(f"/alerts/check/{uid}", headers=headers)

    assert resp.json() == {"newly_triggered": []}
    listed = client.get(f"/alerts/{uid}", headers=headers).json()["alerts"]
    assert listed[0]["triggered"] is False


def test_check_skips_uncrossed_target(client, alert_user, price):
    uid, headers = alert_user
    price["value"] = (90.0, 95.0)

    assert client.get(f"/alerts/check/{uid}", headers=headers).json() == {"newly_triggered": []}
