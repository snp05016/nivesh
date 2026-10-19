"""GH-662 / FINSEC-27: route-level regression coverage for subscription,
entitlements, /api/me, and compliance deletion-request routes.

Each authenticated test uses a throwaway user so tier and deletion-request
state never leak between tests or into the shared session test user.
"""
from __future__ import annotations

import functools
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

_AUTH_ROUTES = [
    ("get", "/api/v1/subscription"),
    ("get", "/api/v1/subscription/entitlements"),
    ("get", "/api/me/subscription"),
    ("get", "/api/me/consent"),
    ("delete", "/api/me/account"),
    ("post", "/api/v1/compliance/deletion-requests"),
    ("post", "/api/v1/compliance/deletion-requests/cancel"),
    ("get", "/api/v1/compliance/deletion-requests/status"),
    ("post", "/api/v1/compliance/consents/withdraw"),
    ("get", "/api/v1/compliance/audit-trail"),
]

_GATED_FEATURE = "sector_rotation"

# FINSEC-03: deletion routes re-authenticate with the account password.
_PASSWORD = "Delete-Me-123"


@functools.cache
def _password_hash() -> str:
    import database

    return database._hash_password(_PASSWORD)


def _new_user_headers() -> dict:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"sub_{uuid4().hex[:12]}", password_hash=_password_hash(), display_name="Subscription Test")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    return {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


@pytest.mark.parametrize("method, path", _AUTH_ROUTES)
def test_requires_auth(client, method, path):
    kwargs = {"json": {}} if method == "post" else {}
    resp = getattr(client, method)(path, **kwargs)
    assert resp.status_code == 401, resp.text


@pytest.mark.parametrize("path", ["/api/v1/subscription", "/api/me/subscription"])
def test_default_tier_is_free(client, path):
    resp = client.get(path, headers=_new_user_headers())
    assert resp.status_code == 200, resp.text
    assert resp.json()["tier"] == "free"


def test_entitlements_free_user(client):
    resp = client.get("/api/v1/subscription/entitlements", headers=_new_user_headers())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tier"] == "free"
    assert body["features"][_GATED_FEATURE] is False


def _seed_pro(headers: dict) -> None:
    """Seed a PRO row through the ORM: there is no purchase route (paid tiers come from App Store verification)."""
    from datetime import datetime, timedelta, timezone

    import database
    from models.db_models import UserSubscription  # pyright: ignore[reportMissingImports]
    from services import subscription_service

    user_id = database.verify_access_token(headers["Authorization"].split()[1])
    assert user_id is not None
    subscription_service.get_or_create_subscription(user_id)
    with database.get_session() as session:
        session.query(UserSubscription).filter(UserSubscription.user_id == user_id).update({
            "tier": "pro", "billing_cycle": "monthly", "is_active": True,
            "renews_at": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30),
        })
        session.commit()


def test_entitlement_gate_402_then_200_after_upgrade(client):
    from core.entitlement_gate import require_entitlement
    from services.entitlement_service import FEATURE_MIN_TIER

    gated = FastAPI()

    @gated.get("/premium")
    def _premium(user_id: int = Depends(require_entitlement(_GATED_FEATURE))):
        return {"user_id": user_id}

    headers = _new_user_headers()
    required_tier = FEATURE_MIN_TIER[_GATED_FEATURE]
    with TestClient(gated) as gated_client:
        assert gated_client.get("/premium").status_code == 401

        denied = gated_client.get("/premium", headers=headers)
        assert denied.status_code == 402, denied.text
        assert denied.json()["detail"]["required_tier"] == required_tier
        assert denied.json()["detail"]["current_tier"] == "free"

        _seed_pro(headers)

        assert gated_client.get("/premium", headers=headers).status_code == 200

    features = client.get("/api/v1/subscription/entitlements", headers=headers).json()["features"]
    assert features[_GATED_FEATURE] is True


def test_deletion_request_round_trip(client):
    headers = _new_user_headers()
    base = "/api/v1/compliance/deletion-requests"

    assert client.get(f"{base}/status", headers=headers).json() == {"status": None}

    created = client.post(base, json={"reason": "test", "password": _PASSWORD}, headers=headers)
    assert created.status_code == 200, created.text
    assert created.json()["created"] is True
    assert created.json()["status"] == "pending"

    duplicate = client.post(base, json={"password": _PASSWORD}, headers=headers)
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["created"] is False
    assert duplicate.json()["id"] == created.json()["id"]

    assert client.get(f"{base}/status", headers=headers).json()["status"] == "pending"

    cancelled = client.post(f"{base}/cancel", headers=headers)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"

    assert client.post(f"{base}/cancel", headers=headers).status_code == 404
    assert client.get(f"{base}/status", headers=headers).json()["status"] == "cancelled"

    trail = client.get("/api/v1/compliance/audit-trail", headers=headers)
    assert trail.status_code == 200, trail.text
    actions = {entry["action"] for entry in trail.json()}
    assert {"account_deletion_requested", "account_deletion_cancelled"} <= actions


def test_disclosure_public(client):
    resp = client.get("/api/v1/compliance/disclosures/privacy_policy")
    assert resp.status_code == 200, resp.text
    assert resp.json()["key"] == "privacy_policy"
    assert client.get("/api/v1/compliance/disclosures/not_a_key").status_code == 404
