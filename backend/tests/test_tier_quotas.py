"""CMON-22: per-tier watchlist / price-alert caps are enforced server-side.

Each test uses a throwaway user so quota counts and tier state never leak
between tests or into the shared session test user.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from services import entitlement_service
from services.entitlement_service import TIER_LIMITS, QuotaExceeded, enforce_quota


def _new_user() -> tuple[int, dict]:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"quota_{uuid4().hex[:12]}", password_hash="x", display_name="Quota Test")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    return user_id, {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


def _add_watchlist(client, user_id: int, headers: dict, n: int):
    return client.post(
        "/watchlist/add",
        json={"user_id": user_id, "ticker": f"QT{n}", "exchange": "NSE", "company_name": f"Quota {n}"},
        headers=headers,
    )


def _add_alert(client, user_id: int, headers: dict, n: int):
    return client.post(
        "/alerts/add",
        json={"user_id": user_id, "ticker": f"QT{n}", "target_price": 100.0 + n, "direction": "above"},
        headers=headers,
    )


def test_free_watchlist_cap_is_402(client):
    user_id, headers = _new_user()
    cap = TIER_LIMITS["watchlist_size"]["free"]
    for n in range(cap):
        resp = _add_watchlist(client, user_id, headers, n)
        assert resp.status_code == 200, resp.text

    resp = _add_watchlist(client, user_id, headers, cap)
    assert resp.status_code == 402, resp.text
    detail = resp.json()["detail"]
    assert detail["required_tier"] == "pro"
    assert detail["current_tier"] == "free"
    assert str(cap) in detail["message"]


def test_free_watchlist_readd_existing_is_not_blocked(client):
    user_id, headers = _new_user()
    cap = TIER_LIMITS["watchlist_size"]["free"]
    for n in range(cap):
        assert _add_watchlist(client, user_id, headers, n).status_code == 200

    resp = _add_watchlist(client, user_id, headers, 0)
    assert resp.status_code == 200, resp.text
    assert resp.json().get("already_exists") is True


def test_free_alert_cap_is_402(client):
    user_id, headers = _new_user()
    cap = TIER_LIMITS["price_alerts"]["free"]
    for n in range(cap):
        resp = _add_alert(client, user_id, headers, n)
        assert resp.status_code == 200, resp.text

    resp = _add_alert(client, user_id, headers, cap)
    assert resp.status_code == 402, resp.text
    assert resp.json()["detail"]["required_tier"] == "pro"


def test_pro_user_higher_cap(client):
    from services import subscription_service

    user_id, headers = _new_user()
    subscription_service.mock_upgrade(user_id, "pro", "monthly")
    cap = TIER_LIMITS["watchlist_size"]["free"]
    for n in range(cap + 1):
        resp = _add_watchlist(client, user_id, headers, n)
        assert resp.status_code == 200, resp.text


def test_enforce_quota_unlimited_and_boundaries(monkeypatch):
    monkeypatch.setattr(entitlement_service, "get_effective_tier", lambda _uid: "super_pro")
    enforce_quota(1, "watchlist_size", 10_000)  # None == unlimited

    monkeypatch.setattr(entitlement_service, "get_effective_tier", lambda _uid: "pro")
    pro_cap = TIER_LIMITS["price_alerts"]["pro"]
    enforce_quota(1, "price_alerts", pro_cap - 1)
    with pytest.raises(QuotaExceeded) as exc:
        enforce_quota(1, "price_alerts", pro_cap)
    assert exc.value.http_detail() == {
        "message": str(exc.value),
        "required_tier": "super_pro",
        "current_tier": "pro",
    }
