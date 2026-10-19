"""Admin ops API (flags, job runs, audit, usage) and the audit rows on user-level admin reads."""
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

import services.audit_service as audit_service
from database import get_session
from models.db_models import AuditLogEntry, FeatureFlag, JobRun, User, UserEvent
from services import feature_flags

NEW_ROUTES = [
    ("get", "/api/v1/admin/flags"),
    ("put", "/api/v1/admin/flags/analytics"),
    ("get", "/api/v1/admin/job-runs"),
    ("get", "/api/v1/admin/job-runs/summary"),
    ("get", "/api/v1/admin/audit"),
    ("get", "/api/v1/admin/analytics/daily"),
]


@pytest.fixture(autouse=True)
def _reset():
    with get_session() as s:
        s.query(FeatureFlag).delete()
        s.commit()
    feature_flags._reset_cache()
    audit_service._last_written.clear()
    yield
    with get_session() as s:
        s.query(FeatureFlag).delete()
        s.commit()
    feature_flags._reset_cache()


def _call(client, method, path, headers=None, **kw):
    if method == "put":
        kw.setdefault("json", {"enabled": True})
    return getattr(client, method)(path, headers=headers or {}, **kw)


def _audit_rows(action):
    with get_session() as s:
        return [(r.user_id, r.details) for r in s.query(AuditLogEntry).filter_by(action=action).order_by(AuditLogEntry.id)]


@pytest.mark.parametrize("method,path", NEW_ROUTES)
def test_new_routes_require_admin(client, auth_headers, method, path):
    assert _call(client, method, path).status_code == 401
    assert _call(client, method, path, auth_headers).status_code == 403


def test_flag_put_flips_and_audits_once(client, admin_headers):
    r = client.get("/api/v1/admin/flags", headers=admin_headers)
    assert r.json()["flags"][0]["key"] == "analytics" and r.json()["flags"][0]["enabled"] is False
    before = len(_audit_rows("admin_flag_changed"))
    r = client.put("/api/v1/admin/flags/analytics", json={"enabled": True}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["flag"]["enabled"] is True and r.json()["flag"]["source"] == "db"
    assert feature_flags.is_enabled("analytics") is True
    rows = _audit_rows("admin_flag_changed")
    assert len(rows) == before + 1
    assert rows[-1][1]["key"] == "analytics" and rows[-1][1]["from"] is False and rows[-1][1]["to"] is True


def test_flag_put_unknown_key_404(client, admin_headers):
    before = len(_audit_rows("admin_flag_changed"))
    r = client.put("/api/v1/admin/flags/nope", json={"enabled": True}, headers=admin_headers)
    assert r.status_code == 404 and r.json()["detail"] == "Unknown flag"
    assert len(_audit_rows("admin_flag_changed")) == before


def test_job_runs_filters_pagination_and_summary(client, admin_headers):
    with get_session() as s:
        s.query(JobRun).filter(JobRun.job_name.like("adm_%")).delete(synchronize_session=False)
        for i in range(5):
            s.add(JobRun(job_name="adm_a", status="failed" if i == 0 else "ok", error="boom" if i == 0 else None))
        s.add(JobRun(job_name="adm_b", status="ok"))
        s.commit()
    page1 = client.get("/api/v1/admin/job-runs?job_name=adm_a&limit=2", headers=admin_headers).json()
    assert len(page1["runs"]) == 2 and page1["next_before_id"] == page1["runs"][-1]["id"]
    page3 = client.get(f"/api/v1/admin/job-runs?job_name=adm_a&limit=2&before_id={page1['next_before_id']}",
                       headers=admin_headers).json()
    page3 = client.get(f"/api/v1/admin/job-runs?job_name=adm_a&limit=2&before_id={page3['next_before_id']}",
                       headers=admin_headers).json()
    assert len(page3["runs"]) == 1 and page3["next_before_id"] is None
    failed = client.get("/api/v1/admin/job-runs?job_name=adm_a&status=failed", headers=admin_headers).json()
    assert [r["error"] for r in failed["runs"]] == ["boom"]
    assert client.get("/api/v1/admin/job-runs?status=bogus", headers=admin_headers).status_code == 422
    summary = client.get("/api/v1/admin/job-runs/summary?days=7", headers=admin_headers).json()
    job = {j["job_name"]: j for j in summary["jobs"]}["adm_a"]
    assert (job["runs"], job["failures"], job["success_pct"]) == (5, 1, 80.0)
    assert client.get("/api/v1/admin/job-runs/summary?days=91", headers=admin_headers).status_code == 422


@pytest.fixture(scope="module")
def actor():
    """A throwaway user for audit rows and events written directly by these tests."""
    with get_session() as s:
        u = User(username=f"admops_{uuid4().hex[:10]}", password_hash="x", display_name="Ops")
        s.add(u)
        s.commit()
        uid = int(u.id)
    yield uid
    with get_session() as s:
        s.query(AuditLogEntry).filter_by(user_id=uid).delete()
        s.query(UserEvent).filter_by(user_id=uid).delete()
        s.query(User).filter_by(id=uid).delete()
        s.commit()


def test_audit_list_prefix_and_pagination(client, admin_headers, actor):
    uid = actor
    for i in range(3):
        audit_service.audit_now(uid, "admin_testprefix", {"i": i})
    audit_service.audit_now(uid, "other_action", {})
    r = client.get("/api/v1/admin/audit?action_prefix=admin_testprefix&limit=2", headers=admin_headers).json()
    assert len(r["entries"]) == 2 and r["next_before_id"] == r["entries"][-1]["id"]
    assert all(e["action"] == "admin_testprefix" and e["created_at"].endswith("Z") for e in r["entries"])
    nxt = client.get(f"/api/v1/admin/audit?action_prefix=admin_testprefix&limit=2&before_id={r['next_before_id']}",
                     headers=admin_headers).json()
    assert len(nxt["entries"]) >= 1 and set(nxt["entries"][0]) >= {"id", "actor_user_id", "details", "ip_address"}
    assert client.get("/api/v1/admin/audit?limit=201", headers=admin_headers).status_code == 422
    assert not any(e["action"] == "other_action" for e in
                   client.get("/api/v1/admin/audit?action_prefix=admin_", headers=admin_headers).json()["entries"])


def test_audit_prefix_wildcards_are_literal(client, admin_headers, actor):
    audit_service.audit_now(actor, "admin_x", {})
    assert audit_service.list_entries(action_prefix="%") == []
    assert audit_service.list_entries(action_prefix="admin_x")


def test_analytics_daily(client, admin_headers, actor):
    uid = actor
    with get_session() as s:
        s.add(UserEvent(user_id=uid, event_name="app_open", created_at=datetime.utcnow() - timedelta(hours=1)))
        s.commit()
    r = client.get("/api/v1/admin/analytics/daily?days=14", headers=admin_headers).json()
    assert r["days"] == 14 and r["active_users"] >= 1 and r["rows"]
    assert client.get("/api/v1/admin/analytics/daily?days=32", headers=admin_headers).status_code == 422


@pytest.mark.parametrize("path,action,check", [
    ("/dashboard-user-data?user_id=987654", "admin_viewed_user", lambda d: d == {"target_user_id": 987654}),
    ("/dashboard-data/analysis/987654", "admin_viewed_analysis", lambda d: d == {"analysis_id": 987654}),
    ("/users", "admin_listed_users", lambda d: d == {}),
    ("/api/v1/admin/error-telemetry", "admin_viewed_error_telemetry", lambda d: d == {}),
    ("/api/v1/dashboard/ai-engine/abc123", "admin_viewed_job", lambda d: d == {"job_id": "abc123"}),
])
def test_user_level_reads_write_one_audit_row(client, admin_headers, path, action, check):
    before = len(_audit_rows(action))
    client.get(path, headers=admin_headers)
    rows = _audit_rows(action)
    assert len(rows) == before + 1
    details = {k: v for k, v in rows[-1][1].items() if k != "_ctx"}
    assert check(details)


def test_ai_engine_list_audit_is_throttled_per_filter_set(client, admin_headers):
    before = len(_audit_rows("admin_listed_jobs"))
    for _ in range(2):
        assert client.get("/api/v1/dashboard/ai-engine?mode=running&limit=20", headers=admin_headers).status_code == 200
    assert len(_audit_rows("admin_listed_jobs")) == before + 1
    client.get("/api/v1/dashboard/ai-engine?mode=recent&limit=20", headers=admin_headers)
    assert len(_audit_rows("admin_listed_jobs")) == before + 2


def test_aggregate_poll_and_audit_list_are_not_audited(client, admin_headers):
    before = len(_audit_rows("admin_viewed_user"))
    client.get("/dashboard-data", headers=admin_headers)
    client.get("/api/v1/admin/audit", headers=admin_headers)
    assert len(_audit_rows("admin_viewed_user")) == before
    assert not any(a.startswith("admin_viewed_dashboard") for a in ["admin_viewed_dashboard"] if _audit_rows(a))


def test_audit_failure_returns_500_and_no_data(client, admin_headers, monkeypatch):
    import routers.user as user_router

    def boom(*_a, **_k):
        raise RuntimeError("audit down")

    monkeypatch.setattr(user_router, "audit_now", boom)
    r = client.get("/users", headers=admin_headers)
    assert r.status_code == 500 and "username" not in r.text
