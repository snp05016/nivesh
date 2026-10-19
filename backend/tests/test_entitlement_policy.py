"""Growth cluster, honest tiering (41 I44): PRO is exactly the three enforced tools, the
pre-launch tier is the stored tier, and nothing that is not a tool is sold.

Each test makes its own user: the conftest user is shared across the session.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from core.entitlement_gate import require_entitlement
from services import entitlement_service
from services.entitlement_service import FEATURE_MIN_TIER

_PRO_TOOLS = {"sector_rotation", "technical_picks", "ideas_for_profit"}
_PAYOFF_BODY = {"spot_price": 100.0, "legs": [{"type": "CALL", "position": "LONG", "strike": 100.0, "premium": 5.0}]}
_VALUATION_PATHS = ("/fundamentals/TCS/valuation", "/api/v1/fundamentals/valuation?ticker=TCS")
_RISK_PATHS = ("/fundamentals/TCS/risk-signals", "/api/v1/fundamentals/risk-signals?ticker=TCS")


def _new_user() -> tuple[int, dict]:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"pol_{uuid4().hex[:12]}", password_hash="x", display_name="Policy Test")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    return user_id, {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


def _gated_app() -> FastAPI:
    gated = FastAPI()

    @gated.get("/gated")
    def _gated(user_id: int = Depends(require_entitlement("sector_rotation"))):
        return {"user_id": user_id}

    return gated


def test_prelaunch_uses_stored_tier(client):
    msg = "beta comp is off by default (RUNBOOK §f); turning it on needs a reviewed PR that updates this test"
    user_id, headers = _new_user()

    resp = client.get("/api/v1/market/sector-rotation", headers=headers)
    assert resp.status_code == 402, msg
    detail = resp.json()["detail"]
    assert detail["required_tier"] == "pro" and detail["current_tier"] == "free"
    assert client.post("/api/v1/options/payoff", json=_PAYOFF_BODY, headers=headers).status_code == 402, msg

    ent = client.get("/api/v1/subscription/entitlements", headers=headers).json()
    assert ent["tier"] == "free", msg
    assert ent["features"] and not any(ent["features"].values()), msg

    from database import get_session
    from models.db_models import UserSubscription  # pyright: ignore[reportMissingImports]

    with get_session() as session:
        session.query(UserSubscription).filter(UserSubscription.user_id == user_id).update({
            "tier": "pro",
            "is_active": True,
            "renews_at": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1),
        })
        session.commit()

    with TestClient(_gated_app()) as gated_client:
        assert gated_client.get("/gated", headers=headers).status_code == 200
    ent = client.get("/api/v1/subscription/entitlements", headers=headers).json()
    assert ent["tier"] == "pro"
    assert set(ent["features"]) == _PRO_TOOLS and all(ent["features"].values())


def test_pro_catalog_is_reviewed_set():
    assert set(FEATURE_MIN_TIER) == _PRO_TOOLS, (
        "PRO may only contain the three reviewed tools; adding a key needs the legal review in "
        "docs/billing/RUNBOOK.md §f and an update to this test"
    )


def test_unknown_key_fails_closed():
    user_id, _ = _new_user()
    assert entitlement_service.has_entitlement(user_id, "no_such_key") is False


def _dependency_names(dependant):
    for dep in dependant.dependencies:
        call = dep.call
        yield getattr(call, "__qualname__", "") or ""
        yield from _dependency_names(dep)


def test_research_routes_never_gated():
    from main import app

    research = [r for r in app.routes if isinstance(r, APIRoute) and r.path.startswith("/api/v1/research")]
    if not research:
        import pytest
        pytest.skip("no /api/v1/research route mounted")
    for route in research:
        assert not any("require_entitlement" in name for name in _dependency_names(route.dependant)), route.path


def test_valuation_and_risk_not_sold(client):
    _, headers = _new_user()
    for path in _VALUATION_PATHS:
        assert client.get(path, headers=headers).status_code in (404, 200), path
    for path in _RISK_PATHS:
        assert client.get(path, headers=headers).status_code == 200, path
    for path in _VALUATION_PATHS + _RISK_PATHS:
        assert client.get(path).status_code == 401, path
