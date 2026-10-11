"""CMKT-13: market.py's yfinance retry/fallback paths log through the module-level
``logging`` import. Without it the first transient error raised NameError (or
UnboundLocalError) inside the except block and the endpoint returned 500.
The AST check for function-local imports lives in test_logging_unbound_regressions.py.
"""
import time
from types import SimpleNamespace

import pandas as pd


def test_nifty_history_retries_after_yf_error(client, monkeypatch):
    from routers import market

    hist = pd.DataFrame({"Close": [22000.0, 22100.5]},
                        index=pd.to_datetime(["2026-10-08", "2026-10-09"]))
    attempts = []

    def _ticker(_sym):
        attempts.append(_sym)
        if len(attempts) == 1:
            raise RuntimeError("rate limit")
        return SimpleNamespace(history=lambda period: hist)

    monkeypatch.setattr(market.yf, "Ticker", _ticker)
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    monkeypatch.setattr(market, "_dcache_get", lambda *_a, **_k: None)
    monkeypatch.setattr(market, "_dcache_set", lambda *_a, **_k: None)

    resp = client.get("/nifty-history?days=5")

    assert resp.status_code == 200, resp.text
    assert len(attempts) == 2
    assert [p["close"] for p in resp.json()["prices"]] == [22000.0, 22100.5]


def test_dashboard_pulse_survives_pulse_fetch_error(client, monkeypatch):
    from routers import market

    def _boom():
        raise RuntimeError("nse down")

    monkeypatch.setattr(market, "fetch_market_pulse", _boom)
    monkeypatch.setattr(market, "fetch_momentum", _boom)
    monkeypatch.setattr(market, "fetch_yoy_aggregate_indicators", lambda: {})
    monkeypatch.setattr(market, "_build_cap_index_grid", lambda: [])

    resp = client.get("/api/v1/market/dashboard-pulse")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["pulse"]["indices"] == []
    assert body["momentum"]["bullish"] == []
