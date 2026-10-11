"""SILENT-06: a router's `except Exception -> HTTPException(500)` keeps its cause in the log."""
import logging

import routers.portfolio as portfolio_router


def test_500_logs_chained_traceback(client, auth_headers, test_user_id, monkeypatch, caplog):
    def _boom(*_a, **_k):
        raise RuntimeError("boom-6")

    monkeypatch.setattr(portfolio_router, "close_position", _boom)

    with caplog.at_level(logging.ERROR, logger="nivesh.main"):
        resp = client.request("DELETE", "/portfolio/remove", headers=auth_headers,
                              json={"user_id": test_user_id, "ticker": "RELIANCE"})

    assert resp.status_code == 500
    assert "boom-6" not in resp.text  # client still gets the generic message
    records = [r for r in caplog.records if r.name == "nivesh.main" and r.exc_info]
    assert any(isinstance(r.exc_info[1], RuntimeError) and "boom-6" in str(r.exc_info[1])
               for r in records)
