"""AUTH-14 / FINSEC-10 / FINSEC-12 / GH-666 / GH-669: premium tiers cannot be
self-granted and unknown feature keys never ungate a route.

/upgrade has no receipt verification, so it is a 404 unless ALLOW_MOCK_PURCHASES=1;
has_entitlement() is False for an unknown key and require_entitlement() refuses one.
"""
import re
from pathlib import Path
from uuid import uuid4

import pytest

from services import entitlement_service

_UPGRADE = "/api/v1/subscription/upgrade"
_BODY = {"tier": "pro", "billing_cycle": "monthly"}
_ROUTERS = Path(__file__).resolve().parent.parent / "routers"


def _new_user() -> tuple[int, dict]:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"ent_{uuid4().hex[:12]}", password_hash="x", display_name="Entitlement Test")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    return user_id, {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


def test_upgrade_is_404_without_mock_purchases(client, monkeypatch):
    monkeypatch.delenv("ALLOW_MOCK_PURCHASES", raising=False)
    _, headers = _new_user()
    assert client.post(_UPGRADE, json=_BODY, headers=headers).status_code == 404
    assert client.get("/api/v1/subscription", headers=headers).json()["tier"] == "free"


def test_upgrade_is_404_when_flag_is_off(client, monkeypatch):
    monkeypatch.setenv("ALLOW_MOCK_PURCHASES", "0")
    _, headers = _new_user()
    assert client.post(_UPGRADE, json=_BODY, headers=headers).status_code == 404


def test_upgrade_works_with_mock_purchases_enabled(client, monkeypatch):
    monkeypatch.setenv("ALLOW_MOCK_PURCHASES", "1")
    _, headers = _new_user()
    resp = client.post(_UPGRADE, json=_BODY, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["tier"] == "pro"


def test_unknown_feature_key_fails_closed():
    user_id, _ = _new_user()
    assert entitlement_service.has_entitlement(user_id, "no_such_key") is False


def test_require_entitlement_rejects_unknown_key():
    from core.entitlement_gate import require_entitlement

    with pytest.raises(ValueError):
        require_entitlement("no_such_key")


def test_every_router_feature_key_is_known():
    keys = set()
    for path in _ROUTERS.glob("*.py"):
        keys.update(re.findall(r"""require_entitlement\(\s*["']([a-z_]+)["']\s*\)""", path.read_text(encoding="utf-8")))
    assert keys, "no require_entitlement() call sites found"
    assert keys <= set(entitlement_service.FEATURE_MIN_TIER), keys - set(entitlement_service.FEATURE_MIN_TIER)
