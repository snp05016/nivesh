import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import lab.api as api
from tests.lab.synth import make_data

KEY = {"X-ML-Engine-Key": "k"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ML_ENGINE_API_KEY", "k")
    data = make_data(n=60)
    data.provenance = {"source": "synthetic", "warnings": []}
    monkeypatch.setattr(api, "_market", lambda *a, **k: data)
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app), data


def body(data, actions=(), **cfg):
    cal = data.calendar()
    return {"config": {"start": cal[0].isoformat(), "end": cal[-1].isoformat(), "universe": ["AAA", "BBB"], **cfg}, "actions": list(actions)}


def test_requires_key(client):
    c, data = client
    assert c.post("/lab/v1/sim/state", json=body(data)).status_code == 401


def test_state_round_trip_and_bad_action(client):
    c, data = client
    r = c.post("/lab/v1/sim/state", json=body(data, [{"type": "order", "symbol": "AAA", "side": "BUY", "qty": 10}, {"type": "advance", "days": 2}]), headers=KEY)
    assert r.status_code == 200
    j = r.json()
    assert j["state"]["fills"] and j["performance"]["final_equity"] > 0
    assert {w["symbol"] for w in j["watchlist"]} == {"AAA", "BBB"}
    bad = c.post("/lab/v1/sim/state", json=body(data, [{"type": "order", "symbol": "AAA", "side": "SELL", "qty": 10}]), headers=KEY)
    assert bad.status_code == 422 and "action 1" in bad.json()["detail"]


def test_history_never_past_asof(client):
    c, data = client
    cal = data.calendar()
    b = body(data)
    r = c.post("/lab/v1/sim/history", json={"config": b["config"], "asof": cal[10].isoformat(), "symbol": "AAA"}, headers=KEY)
    assert r.status_code == 200 and r.json()["bars"][-1]["d"] == cal[10].isoformat()


def test_blind_mode_hides_real_symbols(client):
    c, data = client
    acts = [{"type": "order", "symbol": "STOCK-A", "side": "BUY", "qty": 10}, {"type": "advance", "days": 1}]
    r = c.post("/lab/v1/sim/state", json=body(data, acts, hide_identity=True), headers=KEY)
    text = r.text
    assert r.status_code == 200 and "STOCK-A" in text and '"AAA"' not in text and '"BBB"' not in text


def test_autopsy_endpoint(client):
    c, data = client
    acts = [{"type": "advance", "days": 25}, {"type": "order", "symbol": "AAA", "side": "BUY", "qty": 50, "thesis": "t", "planned_stop": 90},
            {"type": "advance", "days": 5}, {"type": "order", "symbol": "AAA", "side": "SELL", "qty": 50}, {"type": "advance", "days": 1}]
    r = c.post("/lab/v1/sim/autopsy", json={**body(data, acts), "order_id": "o1"}, headers=KEY)
    assert r.status_code == 200
    j = r.json()
    assert j["trades"][0]["verdict"]["quadrant"] in {"earned", "bad_break", "lucky", "predictable_loss"}
    assert {c["variant"] for c in j["counterfactuals"]} >= {"hold_cash", "half_size", "wait_2_sessions"}
    assert c.post("/lab/v1/sim/autopsy", json={**body(data, acts), "order_id": "o9"}, headers=KEY).status_code in (404, 422)


def test_feature_compile_route(client):
    c, _ = client
    ok = c.post("/lab/v1/features/compile", json={"program": "a = close / lag(close, 5) - 1\nb = rank(a)"}, headers=KEY).json()
    assert ok["ok"] and [o["name"] for o in ok["outputs"]] == ["a", "b"]
    bad = c.post("/lab/v1/features/compile", json={"program": "a = lag(close, 0)"}, headers=KEY).json()
    assert not bad["ok"] and bad["line"] == 1


def test_templates_route(client):
    c, _ = client
    j = c.get("/lab/v1/hypothesis/templates", headers=KEY).json()
    assert len(j["templates"]) >= 5 and "close" in j["fields"]


def test_recent_data_embargo(client, monkeypatch):
    from datetime import date, timedelta

    c, data = client
    b = body(data)
    b["config"]["end"] = (date.today() - timedelta(days=5)).isoformat()
    b["config"]["start"] = (date.today() - timedelta(days=200)).isoformat()
    r = c.post("/lab/v1/sim/state", json=b, headers=KEY)
    assert r.status_code == 422 and "30 days" in r.json()["detail"]
    monkeypatch.setenv("LAB_MIN_DATA_AGE_DAYS", "0")
    assert c.post("/lab/v1/sim/state", json=body(data), headers=KEY).status_code == 200


def test_scenarios_marked_by_data_coverage(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(api, "_panel", lambda src: (None, {"first": "2018-01-01", "last": "2026-06-23"}))
    j = c.get("/lab/v1/scenarios", headers=KEY).json()
    by = {s["id"]: s["data_available"] for s in j["scenarios"]}
    assert by and by.get("covid-crash-2020") is True and by.get("gfc-jan-2008-crash") is False
