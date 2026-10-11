"""AUTH-08: job status, active-job, cancel and /batch take the caller from the bearer
token; a body or ?user_id= never selects another user's data."""
import json
from datetime import date
from typing import cast
from uuid import uuid4

import pytest

import database
from models.db_models import AnalysisHistory, User


def _user() -> tuple[int, dict]:
    with database.get_session() as session:
        user = User(username=f"own_{uuid4().hex[:12]}", password_hash="x", display_name="Owner Test")
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = cast(int, user.id)
        return user_id, {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


def _status(job_id: str) -> str:
    job = database.get_job(job_id)
    assert job is not None
    return job["status"]


@pytest.fixture
def jobs():
    """User A's RUNNING job (with a worker pid) and an ownerless job; both end at teardown."""
    a_id, a_headers = _user()
    _b_id, b_headers = _user()
    a_job = database.create_job(a_id, "RELIANCE", "NSE", "standard")["job_id"]
    database.update_job(a_job, status="RUNNING", pid=4242)
    anon_job = database.create_job(None, "TCS", "NSE", "standard")["job_id"]
    yield {"a_id": a_id, "a": a_headers, "b": b_headers, "a_job": a_job, "anon_job": anon_job}
    for job_id in (a_job, anon_job):
        database.update_job(job_id, status="CANCELLED")


def test_job_status_needs_the_owners_token(client, jobs):
    url = f"/analyze/job/{jobs['a_job']}"
    assert client.get(url).status_code == 401
    assert client.get(f"{url}?user_id={jobs['a_id']}").status_code == 401
    assert client.get(f"{url}?user_id={jobs['a_id']}", headers=jobs["b"]).status_code == 404

    resp = client.get(url, headers=jobs["a"])
    assert resp.status_code == 200
    assert resp.json()["job_id"] == jobs["a_job"]
    assert "pid" not in resp.json()


def test_ownerless_job_is_admin_only(client, jobs, admin_headers):
    url = f"/analyze/job/{jobs['anon_job']}"
    assert client.get(url, headers=jobs["a"]).status_code == 404
    assert client.get(url, headers=admin_headers).status_code == 200


def test_active_job_comes_from_the_token(client, jobs):
    assert client.get(f"/analyze/active?user_id={jobs['a_id']}").status_code == 401
    foreign = client.get(f"/analyze/active?user_id={jobs['a_id']}", headers=jobs["b"])
    assert foreign.json() == {"status": "NONE"}

    mine = client.get("/analyze/active", headers=jobs["a"]).json()
    assert mine["job_id"] == jobs["a_job"]
    assert "pid" not in mine


def test_cancel_needs_the_owner_or_an_admin(client, jobs, admin_headers):
    url = f"/analyze/{jobs['a_job']}/cancel"
    assert client.post(url).status_code == 401
    assert client.post(f"{url}?user_id={jobs['a_id']}", headers=jobs["b"]).status_code == 404
    assert _status(jobs["a_job"]) == "RUNNING"

    assert client.post(url, headers=admin_headers).status_code == 200
    assert _status(jobs["a_job"]) == "CANCELLED"


def test_batch_reads_only_the_callers_history(client, jobs):
    ticker = f"ZZ{uuid4().hex[:8].upper()}"
    with database.get_session() as session:
        session.add(AnalysisHistory(user_id=jobs["a_id"], ticker=ticker,
                                    analysis_date=date.today().isoformat(), signal="BULLISH",
                                    full_json=json.dumps({"signal": "BULLISH"})))
        session.commit()
    body = {"tickers": [ticker], "user_id": jobs["a_id"]}

    assert client.post("/batch", json=body).status_code == 401
    foreign = client.post("/batch", json=body, headers=jobs["b"])
    assert foreign.json() == {"results": [{"ticker": ticker, "status": "not_cached"}]}
    mine = client.post("/batch", json={"tickers": [ticker]}, headers=jobs["a"])
    assert mine.json()["results"][0]["status"] == "cached"
