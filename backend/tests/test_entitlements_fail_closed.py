"""AUTH-14 / FINSEC-10 / FINSEC-12 / GH-666 / GH-669: premium tiers cannot be
self-granted and unknown feature keys never ungate a route.

The mock /upgrade and /cancel routes are deleted (404);
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


def test_upgrade_route_gone(client):
    _, headers = _new_user()
    # 404, or 405 where the catch-all OPTIONS route claims the path
    assert client.post(_UPGRADE, json=_BODY, headers=headers).status_code in (404, 405)
    assert client.get("/api/v1/subscription", headers=headers).json()["tier"] == "free"


def test_cancel_route_gone(client):
    _, headers = _new_user()
    assert client.post("/api/v1/subscription/cancel", headers=headers).status_code in (404, 405)


def test_no_mock_purchase_code():
    backend = _ROUTERS.parent
    offenders = []
    for path in backend.rglob("*.py"):
        rel = path.relative_to(backend).parts
        if rel[0] in ("tests", "venv", ".venv", "migrations") or "site-packages" in rel:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(word in text for word in ("mock_upgrade", "mock_cancel", "ALLOW_MOCK_PURCHASES")):
            offenders.append("/".join(rel))
    assert not offenders, offenders


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
