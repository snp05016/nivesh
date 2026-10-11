"""REL-16 — admin dashboard reads the live core.dashboard_state, prices AI calls by vendor,
serves its own CSP, and returns real status codes from /dashboard-user-data."""
import json
from types import SimpleNamespace

import pytest

import core.dashboard_state as ds
import main


@pytest.fixture
def as_admin(monkeypatch):
    # dashboard_data / dashboard_user_data call require_admin(authorization) directly;
    # stub it so these tests do not depend on the ADMIN_TOKEN dev bypass.
    monkeypatch.setattr(main, "require_admin", lambda _authorization=None: 1)


def test_dashboard_data_reflects_core_harvest_status(client, as_admin):
    ds._dash_update_harvest("news", "running")
    try:
        resp = client.get("/dashboard-data")
        assert resp.status_code == 200
        assert resp.json()["harvest_status"]["news"]["status"] == "running"
    finally:
        ds._dash_update_harvest("news", "idle")


def test_unknown_harvest_key_registered():
    key = "bhavcopy_test_key"
    try:
        ds._dash_update_harvest(key, "running")
        assert ds._harvest_status[key]["status"] == "running"
        assert ds._harvest_status[key]["last_run"] is not None
    finally:
        ds._harvest_status.pop(key, None)


def test_log_token_usage_writes_model(tmp_path, monkeypatch):
    log = tmp_path / "t.jsonl"
    monkeypatch.setattr(ds, "TOKEN_LOG_PATH", str(log))
    ds._log_token_usage("x", SimpleNamespace(prompt_tokens=1000, completion_tokens=500), "deepseek-chat")
    entry = json.loads(log.read_text().strip())
    assert entry["model"] == "deepseek-chat"
    assert entry["input_tokens"] == 1000
    assert entry["output_tokens"] == 500


def test_log_token_usage_without_model_is_unknown(tmp_path, monkeypatch):
    log = tmp_path / "t.jsonl"
    monkeypatch.setattr(ds, "TOKEN_LOG_PATH", str(log))
    ds._log_token_usage("x", SimpleNamespace(input_tokens=10, output_tokens=5))
    assert json.loads(log.read_text().strip())["model"] == "unknown"


def test_estimate_cost():
    assert ds.estimate_cost_usd("deepseek-chat", 1_000_000, 0) == pytest.approx(0.14)
    assert ds.estimate_cost_usd("deepseek-reasoner", 1_000_000, 0) == pytest.approx(0.55)
    assert ds.estimate_cost_usd("claude-haiku-4-5", 0, 1_000_000) == pytest.approx(5.0)
    assert ds.estimate_cost_usd("claude-sonnet-4-6", 1_000_000, 0) == pytest.approx(3.0)
    assert ds.estimate_cost_usd("mystery", 1, 1) is None
    assert ds.estimate_cost_usd(None, 1, 1) is None
    assert ds.estimate_cost_usd("unknown", 1, 1) is None


def test_dashboard_cost_buckets_deepseek(client, as_admin, tmp_path, monkeypatch):
    log = tmp_path / "t.jsonl"
    log.write_text(
        json.dumps({"endpoint": "a", "model": "deepseek-chat", "input_tokens": 1000, "output_tokens": 500}) + "\n"
        + json.dumps({"endpoint": "b", "input_tokens": 2000, "output_tokens": 100}) + "\n"
    )
    monkeypatch.setattr(ds, "TOKEN_LOG_PATH", str(log))

    data = client.get("/dashboard-data").json()

    assert data["deepseek_stats"]["calls"] == 1
    assert data["deepseek_stats"]["cost_usd"] == pytest.approx((1000 * 0.14 + 500 * 0.28) / 1_000_000)
    assert data["unknown_stats"]["calls"] == 1
    assert data["unknown_stats"]["input_tokens"] == 2000
    assert data["unknown_stats"]["cost_usd"] is None
    assert data["claude_stats"]["calls"] == 0
    # fake main.py-only caches are gone; the live quick-info cache is reported
    assert set(data["cache_stats"]) == {"quick_info", "scraper"}


def test_admin_page_csp(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "cdnjs.cloudflare.com" in page.headers["content-security-policy"]
    assert "Bearer admin" not in page.text  # page asks for a real admin JWT

    ping = client.get("/ping")
    assert ping.headers["content-security-policy"] == "default-src 'self'"


def test_dashboard_user_data_404(client, as_admin):
    resp = client.get("/dashboard-user-data", params={"user_id": 999_999_999})
    assert resp.status_code == 404
    assert "traceback" not in resp.text


def test_admin_page_escapes_untrusted_strings(client):
    # The page holds a real admin JWT, so attacker-controlled strings (logged request paths,
    # usernames, scraped titles) must be HTML-escaped. The script lives in /admin-assets/admin.js.
    page = client.get("/admin-assets/admin.js").text
    assert "function esc(s)" in page
    assert 'title="${esc(r.path)}">${esc(r.path)}' in page
    assert "${esc(e.path||'-')}" in page
    assert "${esc(u.display_name||u.username)}" in page
    for raw in ("${r.path}", "${e.path", "${u.username}", "${v.title}", "${n.headline}", "cancelAIMonitorJob('${"):
        assert raw not in page, raw
