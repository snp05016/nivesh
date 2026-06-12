from fastapi.testclient import TestClient
from main import app
import database
from database import SessionLocal, AnalysisJob

database.init_db()
client = TestClient(app)

_TEST_UIDS = (991001, 991002)


def setup_module(_):
    """Cancel any leftover QUEUED/RUNNING jobs for test UIDs so tests are idempotent."""
    s = SessionLocal()
    try:
        s.query(AnalysisJob).filter(
            AnalysisJob.user_id.in_(_TEST_UIDS),
            AnalysisJob.status.in_(["QUEUED", "RUNNING"]),
        ).update({"status": "FAILED"}, synchronize_session=False)
        s.commit()
    finally:
        s.close()


def test_extreme_allowed_while_standard_active(monkeypatch):
    uid = 991001
    database.create_job(uid, "RELIANCE", "NSE", "standard")
    spawned = {}
    monkeypatch.setattr("services.job_manager.spawn_job",
                        lambda *a, **k: spawned.update(called=True))
    r = client.post("/analyze", json={
        "ticker": "RELIANCE", "exchange": "NSE",
        "user_id": uid, "scan_type": "extreme", "deep_scan": True})
    assert r.status_code == 202, r.text
    assert r.json()["scan_type"] == "extreme"
    assert spawned.get("called") is True


def test_duplicate_extreme_blocked(monkeypatch):
    uid = 991002
    database.create_job(uid, "TCS", "NSE", "extreme")
    monkeypatch.setattr("services.job_manager.spawn_job", lambda *a, **k: None)
    r = client.post("/analyze", json={
        "ticker": "TCS", "exchange": "NSE",
        "user_id": uid, "scan_type": "extreme", "deep_scan": True})
    assert r.status_code == 409
    assert r.json()["error_code"] == "ALREADY_RUNNING"
