"""AUTH-26 (GH-625, GH-628, GH-159) — utility routes that used to be anonymous now require auth."""
from unittest.mock import patch

import pytest


@pytest.mark.parametrize("method,path", [
    ("POST", "/api/v1/backtests/alpha-validation"),
    ("GET", "/api/v1/backtests/strategy-sweep"),
    ("POST", "/api/v1/backtests/regime-breakdown"),
    ("GET", "/api/v1/backtests/cost-sensitivity"),
    ("GET", "/api/v1/portfolio/advisor-consensus?user_id=1"),
    ("GET", "/harvester/sources"),
    ("POST", "/api/v1/dev/push-mock"),
])
def test_anonymous_request_rejected(client, method, path):
    kwargs = {"json": {"device_token": "abcdef123456"}} if method == "POST" else {}
    resp = client.request(method, path, **kwargs)
    assert resp.status_code == 401, resp.text


def test_cost_sensitivity_hides_exception_text(client, auth_headers):
    with patch("routers.backtests.run_alpha_validation", side_effect=RuntimeError("db path /secret")):
        resp = client.get("/api/v1/backtests/cost-sensitivity", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    presets = resp.json()["presets"]
    assert presets and all(p["error"] == "unavailable" for p in presets.values())
    assert "/secret" not in resp.text


def test_advisor_consensus_bounds_days(client, auth_headers):
    resp = client.get("/api/v1/portfolio/advisor-consensus?days=999", headers=auth_headers)
    assert resp.status_code == 422
    resp = client.get("/api/v1/portfolio/advisor-consensus?days=7", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["window_days"] == 7


def test_push_mock_is_admin_only(client, auth_headers, admin_headers, monkeypatch):
    body = {"device_token": "abcdef123456", "title": "t", "body": "b"}
    assert client.post("/api/v1/dev/push-mock", json=body, headers=auth_headers).status_code == 403

    monkeypatch.setenv("ENVIRONMENT", "development")
    resp = client.post("/api/v1/dev/push-mock", json=body, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "queued"

    monkeypatch.setenv("ENVIRONMENT", "production")
    assert client.post("/api/v1/dev/push-mock", json=body, headers=admin_headers).status_code == 404
