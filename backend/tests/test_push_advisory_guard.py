"""I03 Evidence mode: no push, inbox row or signal-warning reads like a tip.

One filter (advisory_guard.neutralize_push) runs at notify(), with backstops in
notifications_inbox.create_notification and alerts_service.send_apns, and a static
rule that every inbox writer and APNs builder calls it.
"""
import asyncio
import json
import re
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models.db_models import Base, DeviceToken, InAppNotification, User
from services import alerts_service, notifications_inbox
from services.advisory_guard import first_advisory_term, is_advisory_text, neutralize_push

NEUTRAL_TCS = ("Nivesh update", "Open Nivesh for the latest on TCS.")
BACKEND = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# The filter
# ---------------------------------------------------------------------------

def test_tip_is_neutralised_with_ticker():
    assert neutralize_push("TCS — BUY", "Confidence: 80%", "TCS") == (*NEUTRAL_TCS, True)


def test_tip_without_ticker_uses_generic_body():
    assert neutralize_push("Top pick", "x") == ("Nivesh update", "Open Nivesh for details.", True)


def test_price_alert_text_is_unchanged():
    title, body = "TCS price alert", "TCS is now above ₹3,550.00 (last ₹3,600.00)."
    assert neutralize_push(title, body, "TCS") == (title, body, False)


def test_sell_off_is_not_advice():
    assert not is_advisory_text("Markets saw a sell-off")
    assert neutralize_push("Markets saw a sell-off", "")[2] is False


def test_hinglish_is_caught():
    assert is_advisory_text("Kharido abhi")
    assert first_advisory_term("Kharido abhi") == "kharido"


def test_whole_words_only():
    assert not is_advisory_text("Buyback record date announced")
    assert first_advisory_term("Hit the stop-loss") == "stop-loss"


# ---------------------------------------------------------------------------
# Primary path: notification_service.notify() (habit-notif-service)
# ---------------------------------------------------------------------------

def test_notify_stores_and_pushes_neutral_text(client, auth_headers, test_user_id, monkeypatch):
    notification_service = pytest.importorskip("services.notification_service")
    from database import get_session

    calls = []

    def _recorder(user_id, title, body, data):
        calls.append((user_id, title, body, data))
        return "SENT"

    monkeypatch.setattr(notification_service, "_push", _recorder)

    notification_service.notify(test_user_id, "price_alert", "TCS — BUY now", "Confidence 80%",
                                data={"ticker": "TCS"})

    assert len(calls) == 1
    user_id, title, body, data = calls[0]
    assert (user_id, title, body) == (test_user_id, *NEUTRAL_TCS)
    assert data["ticker"] == "TCS"
    nid = data["notification_id"]
    with get_session() as s:
        row = s.get(InAppNotification, nid)
        assert (row.title, row.body) == NEUTRAL_TCS

    resp = client.get("/api/v1/notifications?limit=200", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    item = next(n for n in resp.json() if n["id"] == nid)
    assert item["title"] == "Nivesh update"


# ---------------------------------------------------------------------------
# Backstops
# ---------------------------------------------------------------------------

@pytest.fixture()
def mem_db(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    @contextmanager
    def _get_session():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    for mod in (alerts_service, notifications_inbox):
        monkeypatch.setattr(mod, "get_session", _get_session)
    monkeypatch.setattr(alerts_service, "_provider_tokens", {})
    with _get_session() as s:
        s.add(User(id=1, username="advisory_user", password_hash="x", display_name="A"))
        s.commit()
    yield _get_session
    engine.dispose()


def test_create_notification_neutralises(mem_db):
    nid = notifications_inbox.create_notification(
        1, "morning_brief", "Top pick: TCS", "Buy before results",
        action_url="nivesh://analyze/TCS")
    with mem_db() as s:
        row = s.get(InAppNotification, nid)
        assert (row.title, row.body) == NEUTRAL_TCS
        assert row.action_url == "nivesh://analyze/TCS"


def test_create_notification_keeps_price_alert_text(mem_db):
    nid = notifications_inbox.create_notification(
        1, "price_alert", "TCS alert triggered", "TCS is now above ₹100.00 (current ₹150.00)",
        action_url="nivesh://analyze/TCS")
    with mem_db() as s:
        row = s.get(InAppNotification, nid)
        assert row.title == "TCS alert triggered"


def test_send_apns_pushes_neutral_alert_with_original_data(mem_db, monkeypatch, tmp_path):
    with mem_db() as s:
        s.add(DeviceToken(user_id=1, device_token="c" * 64, platform="ios"))
        s.commit()
    key = tmp_path / "AuthKey.p8"
    key.write_bytes(ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))
    monkeypatch.setenv("APNS_AUTH_KEY_PATH", str(key))
    monkeypatch.setenv("APNS_KEY_ID", "KEYID")
    monkeypatch.setenv("APNS_TEAM_ID", "TEAMID")

    payloads = []

    def _handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return httpx.Response(200)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(alerts_service.httpx, "AsyncClient",
                        lambda *_a, **_k: real_client(transport=httpx.MockTransport(_handler)))

    data = {"ticker": "TCS", "type": "price_alert"}
    result = asyncio.run(alerts_service.send_apns(1, "TCS — SELL", "Bearish signal", data))

    assert result is alerts_service.PushResult.SENT
    assert len(payloads) == 1
    sent = payloads[0]
    assert sent["aps"]["alert"] == {"title": NEUTRAL_TCS[0], "body": NEUTRAL_TCS[1]}
    assert {k: sent[k] for k in data} == data


# ---------------------------------------------------------------------------
# Static rule: every inbox writer and APNs builder runs the filter
# ---------------------------------------------------------------------------

_SKIP_DIRS = {"tests", "migrations", "venv", ".venv", "__pycache__", "node_modules"}
_WRITER_RES = (
    re.compile(r"(?<!def )(?<!\w)create_notification\("),
    re.compile(r"(?<!class )(?<!\w)InAppNotification\("),
    re.compile(r"apns-push-type|/3/device/"),
)


def test_every_inbox_writer_and_apns_builder_calls_neutralize_push():
    writers, offenders = [], []
    for path in BACKEND.rglob("*.py"):
        if _SKIP_DIRS & set(path.relative_to(BACKEND).parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(r.search(text) for r in _WRITER_RES):
            rel = str(path.relative_to(BACKEND))
            writers.append(rel)
            if "neutralize_push(" not in text:
                offenders.append(rel)
    # Not vacuous: the known writers are found.
    assert {"services/alerts_service.py", "services/notifications_inbox.py"} <= set(writers)
    assert offenders == []


# ---------------------------------------------------------------------------
# Signal warnings and the legacy test push
# ---------------------------------------------------------------------------

def test_signal_warnings_empty_unless_advisory_output(client, auth_headers, test_user_id,
                                                      monkeypatch):
    from database import AnalysisHistory, Portfolio, get_session

    ticker = "IOEVDTST"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with get_session() as s:
        s.add(Portfolio(user_id=test_user_id, ticker=ticker, company_name="Evidence Test",
                        shares=1, buy_price=100.0, group_name="holdings"))
        for i, signal in enumerate(("BULLISH", "NEUTRAL")):
            s.add(AnalysisHistory(ticker=ticker, analysis_date="2026-10-0%d" % (i + 1),
                                  signal=signal, confidence_pct=70, full_json="{}",
                                  created_at=now - timedelta(days=2 - i)))
        s.commit()
    url = f"/portfolio/signal-warnings?user_id={test_user_id}"
    try:
        monkeypatch.delenv("ADVISORY_OUTPUT_ENABLED", raising=False)
        resp = client.get(url, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"warnings": []}

        monkeypatch.setenv("ADVISORY_OUTPUT_ENABLED", "true")
        warnings = client.get(url, headers=auth_headers).json()["warnings"]
        assert [w["ticker"] for w in warnings if w["ticker"] == ticker] == [ticker]
    finally:
        with get_session() as s:
            s.query(Portfolio).filter_by(user_id=test_user_id, ticker=ticker).delete()
            s.query(AnalysisHistory).filter_by(ticker=ticker).delete()
            s.commit()


def test_legacy_test_push_route_is_gone():
    from main import app
    assert "/notifications/test" not in {getattr(r, "path", None) for r in app.routes}
