"""C1 golden path, backend half (docs/release/GOLDEN_PATH.md).

One test walks the path a new user takes against the main app (conftest client,
temp SQLite): register, log in, add TCS, priced P&L, open the stock report,
create a price alert, register a device, one poller pass, the push and the inbox
row that opens nivesh://analyze/TCS. Prices, ml-engine, the LLM and APNs are
fakes; TEST-13's socket guard stays on.

Responses are compared with the recordings in docs/contract/golden/ key for key
in both directions at every depth, and by JSON type. Re-record after an intended
API change: cd backend && GOLDEN_RECORD=1 ../venv/bin/python -m pytest tests/test_golden_path.py -q
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import routers.portfolio as portfolio_router
import routers.research as research_router
from models.db_models import Base  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)
from services import alerts_service, llm_utils
from tests.conftest import REGISTER_CONSENT
from tests.test_research_api import FRI_NIGHT, _seed, _set_config

GOLDEN = Path(__file__).resolve().parents[2] / "docs" / "contract" / "golden"
REQUESTS: dict[str, dict[str, Any]] = json.loads((GOLDEN / "requests.json").read_text(encoding="utf-8"))
RERECORD = (
    "If this API change is intended, re-record: cd backend && GOLDEN_RECORD=1 "
    "../venv/bin/python -m pytest tests/test_golden_path.py -q, then commit docs/contract/golden."
)
FIXED_TIME = "2026-01-01T00:00:00Z"
TOKEN_KEYS = {"access_token", "refresh_token", "token"}
TIME_KEYS = {"timestamp", "as_of"}


# ---------------------------------------------------------------------------
# Golden helpers
# ---------------------------------------------------------------------------

def _normalise(obj: Any) -> Any:
    """Recursive copy with tokens, ids, usernames and timestamps fixed."""
    if isinstance(obj, list):
        return [_normalise(v) for v in obj]
    if not isinstance(obj, dict):
        return obj
    out = {}
    for key, value in obj.items():
        is_int = isinstance(value, int) and not isinstance(value, bool)
        if key in TOKEN_KEYS and isinstance(value, str):
            value = "<token>"
        elif key == "username" and isinstance(value, str):
            value = "golden_user"
        elif key == "user_id" and is_int:
            value = 7
        elif (key == "id" or key.endswith("_id")) and is_int:
            value = 1
        elif (key.endswith("_at") or key in TIME_KEYS) and isinstance(value, str):
            value = FIXED_TIME
        else:
            value = _normalise(value)
        out[key] = value
    return out


def _kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return {str: "string", dict: "object", list: "array"}.get(type(value), type(value).__name__)


def _same_shape(recorded: Any, actual: Any, path: str = "$") -> None:
    """Fail unless `actual` has exactly the recorded keys at every depth and the same JSON types."""
    if recorded is None:  # a recorded null: the key exists (checked by the parent), any value
        return
    if _kind(actual) != _kind(recorded):
        pytest.fail(f"{path}: expected {_kind(recorded)}, got {_kind(actual)}. {RERECORD}")
    if isinstance(recorded, dict):
        missing = sorted(f"{path}.{k}" for k in recorded.keys() - actual.keys())
        extra = sorted(f"{path}.{k}" for k in actual.keys() - recorded.keys())
        if missing or extra:
            pytest.fail(f"{path}: missing keys {missing}, extra keys {extra}. {RERECORD}")
        for key, value in recorded.items():
            _same_shape(value, actual[key], f"{path}.{key}")
    elif isinstance(recorded, list) and recorded:
        for i, item in enumerate(actual):
            _same_shape(recorded[0], item, f"{path}[{i}]")


def check_golden(name: str, body: Any) -> None:
    """Record (GOLDEN_RECORD=1) or compare one response with docs/contract/golden/<name>.json."""
    path = GOLDEN / f"{name}.json"
    if os.environ.get("GOLDEN_RECORD") == "1":
        path.write_text(json.dumps(_normalise(body), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        return
    _same_shape(json.loads(path.read_text(encoding="utf-8")), _normalise(body))


@contextmanager
def _research_db(monkeypatch):
    """A private in-memory DB behind routers.research (as test_research_api does), so the
    seeded TCS report never reaches the session-wide test DB other tests read."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    @contextmanager
    def _get_session():
        try:
            yield session
        except Exception:
            session.rollback()
            raise

    monkeypatch.setattr(research_router, "get_session", _get_session)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class _NoComputeEngine:
    def compute(self, symbol: str):
        pytest.fail(f"GET /stocks/{symbol} must serve the stored report, not compute one")


# ---------------------------------------------------------------------------
# The path
# ---------------------------------------------------------------------------

def test_golden_path(client, monkeypatch):
    # 1. Register, then log in.
    username = f"golden_{uuid.uuid4().hex[:8]}"
    register = {**REQUESTS["register"], **REGISTER_CONSENT, "username": username}
    resp = client.post("/register", json=register)
    assert resp.status_code == 200, resp.text
    resp = client.post("/login", json={**REQUESTS["login"], "username": username})
    assert resp.status_code == 200, resp.text
    login = resp.json()
    check_golden("login", login)
    uid = login["user_id"]
    auth = {"Authorization": f"Bearer {login['access_token']}"}

    # 2. Add the holding (prices are fakes from here on).
    monkeypatch.setattr(portfolio_router, "_to_ns", lambda t: f"{t}.NS")
    monkeypatch.setattr(portfolio_router, "_yf_price", lambda _sym: (3600.0, 3580.0))
    resp = client.post("/portfolio/add", json={**REQUESTS["add_holding"], "user_id": uid}, headers=auth)
    assert resp.status_code == 200, resp.text

    # 3. Priced P&L: 10 x (3600 - 3500).
    monkeypatch.setattr(portfolio_router, "_yf_price_with_status",
                        lambda _sym: (3600.0, 3580.0, "live", "2026-01-01T09:15:00+00:00"))
    resp = client.get(f"/portfolio/{uid}", headers=auth)
    assert resp.status_code == 200, resp.text
    portfolio = resp.json()
    check_golden("portfolio", portfolio)
    assert portfolio["holdings"][0]["ticker"] == "TCS"
    assert portfolio["holdings"][0]["pnl_inr"] == 1000.0

    # 4. The stored stock report, served without computing or calling the LLM.
    _set_config(monkeypatch, mode="on")
    monkeypatch.setattr(research_router, "_now", lambda: FRI_NIGHT)
    monkeypatch.setattr(research_router, "MLEngineClient", lambda *a, **k: _NoComputeEngine())
    monkeypatch.setattr(llm_utils, "deepseek_chat",
                        MagicMock(side_effect=AssertionError("no LLM call on a request path")))
    with _research_db(monkeypatch) as rsession:
        _seed(rsession, "no_edge.json", symbol="TCS")
        resp = client.get("/api/v1/research/stocks/TCS", headers=auth)
    assert resp.status_code == 200, resp.text
    assert resp.json()["symbol"] == "TCS"

    # 5. Price alert. Quotes and the APNs recorder go in first, so whichever poller
    # pass claims the alert (this test's, or the app's background one) is faked.
    monkeypatch.setattr(alerts_service, "_to_ns", lambda t: f"{t}.NS")
    monkeypatch.setattr(alerts_service, "_yf_price",
                        lambda sym: (3600.0, None) if sym == "TCS.NS" else (None, None))
    pushes: list[dict[str, Any]] = []

    async def _record_push(user_id, title, body, data=None):
        pushes.append({"user_id": user_id, "title": title, "body": body, "data": data or {}})
        return alerts_service.PushResult.SENT

    # habit-notif-service routes pushes through notification_service, which may bind send_apns itself.
    senders = [alerts_service]
    if importlib.util.find_spec("services.notification_service") is not None:
        import services.notification_service as notification_service  # pyright: ignore[reportMissingImports]
        if hasattr(notification_service, "send_apns"):
            senders.append(notification_service)
    for module in senders:
        monkeypatch.setattr(module, "send_apns", _record_push)

    resp = client.post("/alerts/add", json={**REQUESTS["add_alert"], "user_id": uid}, headers=auth)
    assert resp.status_code == 200, resp.text
    check_golden("add_alert", resp.json())
    resp = client.get(f"/alerts/{uid}", headers=auth)
    assert resp.status_code == 200, resp.text
    alerts = resp.json()
    assert len(alerts["alerts"]) == 1
    check_golden("alerts", alerts)

    # 6. Device token.
    resp = client.post("/api/v1/notifications/register",
                       json={**REQUESTS["device_register"], "user_id": uid}, headers=auth)
    assert resp.status_code == 200, resp.text

    # 7. One poller pass: 3600 crosses 'above 3550'.
    asyncio.run(alerts_service._poll_once())

    # 8. Exactly one push, then the inbox row that opens the stock.
    mine = [p for p in pushes if p["user_id"] == uid]
    assert len(mine) == 1, mine
    assert mine[0]["data"].get("ticker") == "TCS"
    resp = client.get("/api/v1/notifications", headers=auth)
    assert resp.status_code == 200, resp.text
    inbox = resp.json()
    assert inbox and inbox[0]["action_url"] == "nivesh://analyze/TCS"
    if importlib.util.find_spec("services.notification_service") is not None:
        # notify() adds the inbox row id to the payload (habit-notif-service); the tap marks it opened.
        assert mine[0]["data"].get("notification_id") == inbox[0]["id"]
    check_golden("inbox", inbox)
