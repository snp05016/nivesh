"""Task 6 — job_worker drives a job to a terminal state and stores the result."""
import pytest


@pytest.fixture(scope="module", autouse=True)
def _ensure_table():
    import database
    database.Base.metadata.create_all(database.ENGINE)


def test_worker_marks_succeeded(monkeypatch):
    import database
    import services.job_worker as jw
    job = database.create_job(11_111_111, "RELIANCE", "NSE", "standard")

    # analyze is imported at call-time from services.orchestrator → patch the source
    monkeypatch.setattr("services.orchestrator.analyze",
                        lambda *a, **k: {"signal": "BUY", "confidence_pct": 71})
    # don't actually arm a 5-minute watchdog thread during the test
    monkeypatch.setattr(jw, "_start_wallclock_watchdog", lambda *a, **k: None)

    jw.run_job(job["job_id"], "RELIANCE", "NSE", 11_111_111, False, "standard")

    g = database.get_job(job["job_id"])
    assert g["status"] == "SUCCEEDED"
    assert g["progress_pct"] == 100
    assert g["result"] == {"signal": "BUY", "confidence_pct": 71}


def test_worker_marks_failed(monkeypatch):
    import database
    import services.job_worker as jw
    job = database.create_job(11_111_112, "TCS", "NSE", "standard")

    def _boom(*a, **k):
        raise RuntimeError("deepseek down")

    monkeypatch.setattr("services.orchestrator.analyze", _boom)
    monkeypatch.setattr(jw, "_start_wallclock_watchdog", lambda *a, **k: None)

    with pytest.raises(RuntimeError):
        jw.run_job(job["job_id"], "TCS", "NSE", 11_111_112, False, "standard")

    g = database.get_job(job["job_id"])
    assert g is not None
    assert g["status"] == "FAILED"
    # The raw exception stays in the server log; the owner polls generic text (AUTH-08).
    assert g["error"] == "Analysis failed. Please try again."
    assert all("deepseek down" not in cp["message"] for cp in g["checkpoints"])
