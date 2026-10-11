"""PERF-23: responses of 1 KB or more are gzip-compressed when the client asks for it;
small responses and the SSE stream are sent as-is."""
GZIP = {"Accept-Encoding": "gzip"}


def test_large_json_gzipped(client):
    resp = client.get("/openapi.json", headers=GZIP)  # docs are on in tests (conftest)
    assert resp.status_code == 200
    assert len(resp.content) > 1024
    assert resp.headers.get("content-encoding") == "gzip"
    assert "paths" in resp.json()  # the client still decodes it transparently


def test_small_not_gzipped(client):
    resp = client.get("/ping", headers=GZIP)
    assert resp.status_code == 200
    assert "content-encoding" not in resp.headers


def test_sse_not_gzipped(client, admin_headers, monkeypatch):
    from routers import dashboard

    monkeypatch.setattr(dashboard, "_STREAM_MAX_SEC", 0)  # one frame, then the stream ends
    monkeypatch.setattr(dashboard, "get_dashboard_snapshot", lambda: {"type": "dashboard_snapshot"})

    resp = client.get("/api/v1/dashboard/stream", headers={**admin_headers, **GZIP})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "content-encoding" not in resp.headers
    assert resp.text.startswith("data: ")
