"""POST /api/v1/events, GET /api/v1/flags fields, erase on consent withdrawal, daily counts.

Routers are mounted on a fresh FastAPI() with require_auth stubbed by Authorization: Bearer <id>.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.rate_limiter as rate_limiter
import core.security as security
from database import ENGINE, get_session
from models.db_models import Base, FeatureFlag, KYCConsent, User, UserEvent
from routers import events as events_router
from routers import flags as flags_router
from services import compliance_service, events_service, feature_flags, kyc_consent_service, retention
from services.disclosure_service import CONSENT_PURPOSES


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    Base.metadata.create_all(ENGINE)
    monkeypatch.delenv("FEATURE_ANALYTICS", raising=False)
    with get_session() as s:
        s.query(FeatureFlag).delete()
        s.commit()
    feature_flags._reset_cache()
    rate_limiter._rate_limit_store.clear()
    # Tokens are "Bearer <user id>" in these tests.
    monkeypatch.setattr(security, "verify_access_token", lambda t: int(t) if t.isdigit() else None)
    yield
    feature_flags._reset_cache()
    rate_limiter._rate_limit_store.clear()


@pytest.fixture
def api():
    app = FastAPI()
    app.include_router(events_router.router)
    app.include_router(flags_router.router)
    return TestClient(app)


def _user() -> int:
    with get_session() as s:
        u = User(username=f"evapi_{uuid4().hex[:12]}", password_hash="x", display_name="E")
        s.add(u)
        s.commit()
        return int(u.id)


def _flag(on=True):
    feature_flags.set_flag("analytics", on, actor_id=1)


def _hdr(uid):
    return {"Authorization": f"Bearer {uid}"}


def _count(uid):
    with get_session() as s:
        return s.query(UserEvent).filter(UserEvent.user_id == uid).count()


def _batch(*names, **extra):
    return {"events": [{"name": n, "props": {}} for n in names], "app_version": "1.4.0", "platform": "ios", **extra}


def _grant(uid):
    kyc_consent_service.record_consent(uid, "product_analytics", True)


def test_requires_token(api):
    assert api.post("/api/v1/events", json=_batch("stock_view")).status_code == 401


def test_flag_off_is_disabled(api):
    uid = _user()
    r = api.post("/api/v1/events", json=_batch("stock_view"), headers=_hdr(uid))
    assert r.status_code == 202 and r.json() == {"accepted": 0, "rejected": 1, "reason": "disabled"}
    assert _count(uid) == 0


def test_no_consent(api):
    _flag()
    uid = _user()
    r = api.post("/api/v1/events", json=_batch("stock_view"), headers=_hdr(uid))
    assert r.json()["reason"] == "no_consent" and _count(uid) == 0


def test_stored_under_token_user_not_body_user(api):
    _flag()
    uid, other = _user(), _user()
    _grant(uid)
    body = _batch("stock_view", user_id=other)
    body["events"][0]["user_id"] = other
    r = api.post("/api/v1/events", json=body, headers=_hdr(uid))
    assert r.json() == {"accepted": 1, "rejected": 0, "reason": None}
    assert _count(uid) == 1 and _count(other) == 0


def test_invalid_events_rejected(api):
    _flag()
    uid = _user()
    _grant(uid)
    body = {"events": [
        {"name": "nope"},
        {"name": "app_open", "props": {"ticker": "TCS"}},
        {"name": "app_open", "props": {"launch": "hot"}},
        {"name": "stock_view", "props": {"launch": "cold"}},
        {"name": "app_open", "props": {"launch": "cold"}},
    ]}
    r = api.post("/api/v1/events", json=body, headers=_hdr(uid))
    assert r.json() == {"accepted": 1, "rejected": 4, "reason": None}


def test_batch_size_limits(api):
    _flag()
    uid = _user()
    assert api.post("/api/v1/events", json=_batch(*["stock_view"] * 51), headers=_hdr(uid)).status_code == 422
    assert api.post("/api/v1/events", json={"events": []}, headers=_hdr(uid)).status_code == 422


def test_ts_clamped(api):
    _flag()
    uid = _user()
    _grant(uid)
    now = datetime.now(timezone.utc)
    body = {"events": [
        {"name": "stock_view", "ts": (now - timedelta(days=30)).isoformat()},
        {"name": "stock_view", "ts": (now - timedelta(days=1)).isoformat()},
    ]}
    api.post("/api/v1/events", json=body, headers=_hdr(uid))
    with get_session() as s:
        times = sorted(r.created_at for r in s.query(UserEvent).filter(UserEvent.user_id == uid))
    naive_now = now.replace(tzinfo=None)
    assert abs((times[1] - naive_now).total_seconds()) < 60  # 30 days old -> now
    assert abs((times[0] - (naive_now - timedelta(days=1))).total_seconds()) < 60


def test_rate_limit(api, monkeypatch):
    _flag()
    monkeypatch.setitem(rate_limiter._RATE_LIMITS, "events", {"window": 3600, "max_requests": 2})
    uid = _user()
    codes = [api.post("/api/v1/events", json=_batch("stock_view"), headers=_hdr(uid)).status_code for _ in range(3)]
    assert codes == [202, 202, 429]


def test_flags_analytics_consented(api):
    _flag()
    uid = _user()
    r = api.get("/api/v1/flags")
    assert r.json()["flags"] == {"analytics": True, "analytics_consented": False}
    assert api.get("/api/v1/flags", headers=_hdr(uid)).json()["flags"]["analytics_consented"] is False
    _grant(uid)
    r = api.get("/api/v1/flags", headers=_hdr(uid))
    assert r.json()["flags"]["analytics_consented"] is True
    assert r.json()["analytics_retention_days"] == retention.USER_EVENTS_RETENTION_DAYS
    assert "no-store" in r.headers["cache-control"] and r.headers["vary"] == "Authorization"
    assert api.get("/api/v1/flags").json()["flags"]["analytics_consented"] is False  # no token
    _flag(False)
    assert api.get("/api/v1/flags", headers=_hdr(uid)).json()["flags"]["analytics_consented"] is False


def test_daily_counts_ist_bucket_and_active_users():
    uid = _user()
    with get_session() as s:
        s.add(UserEvent(user_id=uid, event_name="app_open", created_at=datetime(2026, 10, 10, 19, 0)))
        s.commit()
    out = events_service.daily_counts(days=31)
    mine = [r for r in out["rows"] if r["date"] == "2026-10-11" and r["event_name"] == "app_open"]
    assert mine and mine[0]["users"] >= 1
    assert out["active_users"] >= 1 and events_service.daily_counts(days=999)["days"] == 31


def _seed_three_events(uid):
    with get_session() as s:
        s.add_all([UserEvent(user_id=uid, event_name="stock_view") for _ in range(3)])
        s.commit()


@pytest.mark.parametrize("path", ["revoke", "record", "withdraw"])
def test_withdrawal_erases_events(path):
    uid = _user()
    _grant(uid)
    _seed_three_events(uid)
    assert _count(uid) == 3
    if path == "revoke":
        kyc_consent_service.revoke_consent(uid, "product_analytics")
    elif path == "record":
        kyc_consent_service.record_consent(uid, "product_analytics", False)
    else:
        compliance_service.withdraw_consent(uid, "product_analytics")
    assert _count(uid) == 0
    assert not kyc_consent_service.has_active_consent(uid, "product_analytics")


def test_erase_failure_does_not_break_withdrawal(monkeypatch):
    uid = _user()
    _grant(uid)
    _seed_three_events(uid)

    def boom(_uid):
        raise RuntimeError("erase failed")

    monkeypatch.setattr(events_service, "erase_user_events", boom)
    result = kyc_consent_service.revoke_consent(uid, "product_analytics")
    assert result["revoked"] is True
    assert not kyc_consent_service.has_active_consent(uid, "product_analytics")
    assert _count(uid) == 3  # the daily retention backstop removes them
    retention.run_retention()
    assert _count(uid) == 0


def test_other_consent_withdrawal_keeps_events():
    uid = _user()
    _grant(uid)
    _seed_three_events(uid)
    kyc_consent_service.record_consent(uid, "ai_processing", True)
    kyc_consent_service.revoke_consent(uid, "ai_processing")
    assert _count(uid) == 3


def test_purpose_text_has_retention():
    assert str(retention.USER_EVENTS_RETENTION_DAYS) in CONSENT_PURPOSES["product_analytics"]
    assert "deletes the events" in CONSENT_PURPOSES["product_analytics"]


def test_validate_rules():
    assert events_service.validate("import_done", {"kind": "cas", "outcome": "ok"})
    assert not events_service.validate("import_done", {"kind": "cas", "outcome": "ok", "a": "b", "c": "d", "e": "f"})
    assert not events_service.validate("search", {"results": 5})
    assert not events_service.validate("search", "x")
    assert events_service.validate("stock_view", None)
