"""Task 8 — /analyze returns 202 immediately, enforces one-per-user, polls & cancels."""
import random

import pytest


@pytest.fixture(scope="module", autouse=True)
def _ensure_table():
    import database
    database.Base.metadata.create_all(database.ENGINE)


@pytest.fixture
def api_client(monkeypatch):
    # never spawn a real subprocess during API tests
    import services.job_manager as jm
    monkeypatch.setattr(jm, "spawn_job", lambda *a, **k: None)
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


def _uid():
    uid = random.randint(30_000_000, 39_999_999)
    import database
    from models.db_models import User
    with database.get_session() as session:
        session.add(User(id=uid, username=f"test_{uid}", password_hash="x", display_name="Test"))
        session.commit()
    return uid


def test_analyze_returns_202_immediately(api_client):
    import database
    uid = _uid()
    r = api_client.post("/analyze", json={"ticker": "RELIANCE", "exchange": "NSE",
                                      "user_id": uid, "scan_type": "extreme"})
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "QUEUED"
    jid = body["job_id"]
    assert database.get_job(jid)["status"] in ("QUEUED", "RUNNING")


def test_second_job_blocked_with_409(api_client):
    uid = _uid()
    api_client.post("/analyze", json={"ticker": "A", "exchange": "NSE", "user_id": uid})
    r2 = api_client.post("/analyze", json={"ticker": "B", "exchange": "NSE", "user_id": uid})
    assert r2.status_code == 409
    assert "job_id" in r2.json()
    assert r2.json()["error_code"] == "ALREADY_RUNNING"


def test_job_poll_and_cancel(api_client):
    import database
    uid = _uid()
    jid = api_client.post("/analyze",
                      json={"ticker": "INFY", "exchange": "NSE", "user_id": uid}).json()["job_id"]
    poll = api_client.get(f"/analyze/job/{jid}")
    assert poll.status_code == 200
    assert poll.json()["status"] in ("QUEUED", "RUNNING")

    cancel = api_client.post(f"/analyze/{jid}/cancel")
    assert cancel.status_code == 200
    assert database.get_job(jid)["status"] == "CANCELLED"


def test_active_endpoint(api_client):
    uid = _uid()
    assert api_client.get(f"/analyze/active?user_id={uid}").json()["status"] == "NONE"
    jid = api_client.post("/analyze",
                      json={"ticker": "TCS", "exchange": "NSE", "user_id": uid}).json()["job_id"]
    active = api_client.get(f"/analyze/active?user_id={uid}").json()
    assert active["job_id"] == jid


def test_job_not_found(api_client):
    assert api_client.get("/analyze/job/doesnotexist").status_code == 404
