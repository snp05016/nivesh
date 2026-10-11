"""SILENT-12: POST /api/v1/telemetry/client-error logs an anonymised iOS error line."""
import json
import logging

_URL = "/api/v1/telemetry/client-error"
_BODY = {
    "endpoint": "/portfolio/summary",
    "status": 500,
    "error_kind": "INFRASTRUCTURE_EXCEPTION",
    "message": "The request timed out.",
    "app_version": "2.4.0",
}


def test_requires_auth(client):
    assert client.post(_URL, json=_BODY).status_code == 401


def test_logs_warning(client, auth_headers, test_user_id, caplog):
    with caplog.at_level(logging.WARNING, logger="nivesh.client"):
        resp = client.post(_URL, json=_BODY, headers=auth_headers)

    assert resp.status_code == 202
    lines = [json.loads(r.getMessage()) for r in caplog.records if r.name == "nivesh.client"]
    assert len(lines) == 1
    assert lines[0]["endpoint"] == "/portfolio/summary"
    assert lines[0]["status"] == 500
    assert lines[0]["user_id"] == test_user_id


def test_rejects_oversize(client, auth_headers):
    resp = client.post(_URL, json={**_BODY, "message": "x" * 5000}, headers=auth_headers)
    assert resp.status_code in (413, 422)


def test_rejects_oversize_field(client, auth_headers):
    resp = client.post(_URL, json={**_BODY, "endpoint": "/" + "a" * 300}, headers=auth_headers)
    assert resp.status_code == 422
