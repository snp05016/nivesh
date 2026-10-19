"""ARCH-05 regression: the admin dashboard reads the single dashboard state in core.dashboard_state.

Previously main.py kept shadow copies (state dicts, DataHarvestingError) that
nothing wrote, so the admin dashboard was blind and documented 503s became 500s.
"""
import uuid

import core.dashboard_state as dash
import helpers
import main
import routers.admin_dashboard as admin_router
import services.admin_dashboard_service as admin_svc


def test_dashboard_reads_core_dashboard_state():
    # The admin payload builder reads the live module, never a copy (REL-15).
    assert admin_svc._ds is dash
    # main keeps no state of its own; the write helpers live only in core (re-exported by helpers)
    for name in ("_active_analyses", "_completed_analyses", "_request_log", "_token_stats",
                 "_harvest_status", "_dash_start_job", "_dash_end_job", "_dash_update_harvest",
                 "_log_token_usage"):
        assert not hasattr(main, name), name


def test_single_data_harvesting_error_class():
    assert main.DataHarvestingError is helpers.DataHarvestingError


def test_market_scrape_failure_returns_503(client, monkeypatch):
    import routers.earnings as earnings

    def _boom():
        raise RuntimeError("upstream scrape failed")

    monkeypatch.setattr(earnings, "fetch_earnings_sync_ratio", _boom)
    resp = client.get("/api/v1/earnings/sync-ratio")
    assert resp.status_code == 503, resp.text
    assert resp.json()["detail"].startswith("Market data source temporarily unavailable")
    assert "upstream scrape failed" not in resp.text  # REL-17: no upstream error text


def test_dashboard_data_lists_job_started_via_helpers(client, monkeypatch):
    monkeypatch.setattr(admin_router, "require_admin", lambda *_a, **_k: 1)
    monkeypatch.setattr(admin_svc, "build_ai_engine_monitor", lambda **_k: {})
    job_id = f"arch05-{uuid.uuid4().hex[:8]}"
    helpers._dash_start_job(job_id, "TCS", "NSE", 1)
    try:
        resp = client.get("/dashboard-data", headers={"Authorization": "Bearer x"})
        assert resp.status_code == 200, resp.text
        active_ids = {a.get("job_id") for a in resp.json()["active_analyses"]}
        assert job_id in active_ids
    finally:
        helpers._dash_end_job(job_id, error="test cleanup")


def test_request_log_middleware_writes_core_log(client):
    marker = f"arch05-{uuid.uuid4().hex[:8]}"
    client.get("/health", params={"marker": marker})
    with dash._dash_lock:
        entries = list(dash._request_log)
    assert any(e["path"] == "/health" and e["params"].get("marker") == marker for e in entries)
