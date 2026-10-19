"""Acceptance journeys at the engine level (the backend adds auth and persistence on top)."""
from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

import lab.api as api
from lab.data import Bar, NewsItem
from lab.school import BEHAVIOUR_TO_CONCEPTS, load_curriculum
from tests.lab.synth import make_data, weekdays

KEY = {"X-ML-Engine-Key": "k"}


def _client(monkeypatch, data):
    monkeypatch.setenv("ML_ENGINE_API_KEY", "k")
    monkeypatch.setattr(api, "_market", lambda *a, **k: data)
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def test_journey_beginner_trade_review_lesson(monkeypatch):
    """Start a past session, analyse a stock, buy on a headline with an oversized position,
    live through a crash, ask why it failed, and get a lesson aimed at what went wrong."""
    days = weekdays(date(2021, 1, 4), 90)
    crash = [Bar(d, 100 + i * 0.2, 101 + i * 0.2, 99 + i * 0.2, 100 + i * 0.2, 2e6) for i, d in enumerate(days[:60])]
    crash += [Bar(d, 112 - 2 * i, 113 - 2 * i, 110 - 2 * i, 111 - 2 * i, 3e6) for i, d in enumerate(days[60:])]
    data = make_data(n=90, CRS=crash)
    data.news = [NewsItem("CRS", days[58], "Company announces record quarterly orders", "test wire"),
                 NewsItem("CRS", days[70], "Regulator opens inquiry", "test wire")]
    data.__post_init__()
    c = _client(monkeypatch, data)
    cfg = {"start": days[0].isoformat(), "end": days[-1].isoformat(), "universe": ["CRS", "AAA"], "capital": 1_000_000}

    # 1. Analyse: the chart and news stop at the simulated date.
    acts = [{"type": "advance", "days": 58}]
    s = c.post("/lab/v1/sim/state", json={"config": cfg, "actions": acts}, headers=KEY).json()
    assert s["state"]["clock"] == days[58].isoformat()
    assert [n["title"] for n in s["news"]] == ["Company announces record quarterly orders"]
    h = c.post("/lab/v1/sim/history", json={"config": cfg, "asof": s["state"]["clock"], "symbol": "CRS"}, headers=KEY).json()
    assert h["bars"][-1]["d"] == days[58].isoformat()

    # 2. Trade: all-in on the headline, no stop, then hold through the fall and sell late.
    acts += [{"type": "order", "symbol": "CRS", "side": "BUY", "qty": 8000, "thesis": "record orders headline"},
             {"type": "advance", "days": 20},
             {"type": "order", "symbol": "CRS", "side": "SELL", "qty": 8000},
             {"type": "advance", "days": 1}]
    s = c.post("/lab/v1/sim/state", json={"config": cfg, "actions": acts}, headers=KEY).json()
    assert s["performance"]["total_return"] < 0
    assert "Regulator opens inquiry" in [n["title"] for n in s["news"]]

    # 3. Ask why it failed: the autopsy separates what was knowable from hindsight.
    a = c.post("/lab/v1/sim/autopsy", json={"config": cfg, "actions": acts, "order_id": "o1"}, headers=KEY).json()
    t = a["trades"][0]
    assert t["knowable"]["asof"] == days[58].isoformat()
    assert t["knowable"]["news_visible"][0]["title"] == "Company announces record quarterly orders"
    assert all(n["date"] <= t["knowable"]["asof"] for n in t["knowable"]["news_visible"])
    assert t["verdict"]["quadrant"] == "predictable_loss"
    failed = {ch["id"] for ch in t["process"]["checks"] if not ch["passed"]}
    assert {"exit_plan", "size_within_budget"} <= failed
    cf = {x["variant"]: x for x in a["counterfactuals"]}
    assert cf["half_size"]["delta_vs_actual"] > 0 and cf["hold_cash"]["delta_vs_actual"] > 0
    flags = [f["id"] for f in a["behaviour"]]
    assert "concentration" in flags

    # 4. Learn: the school points at the measured weakness.
    nxt = c.post("/lab/v1/school/next", json={"state": None, "weaknesses": flags, "k": 3}, headers=KEY).json()["lessons"]
    assert nxt and all("weakness" in l["reason"] for l in nxt)  # a beginner first gets the prerequisites of the targeted lesson
    targeted = set(BEHAVIOUR_TO_CONCEPTS["concentration"])
    cur = load_curriculum()["lessons"]
    lessons_for_flag = {l["id"] for l in cur if targeted & set(l["concepts"])}
    prereqs = {p for l in cur if l["id"] in lessons_for_flag for p in l["prereqs"]}
    assert {l["id"] for l in nxt} & (lessons_for_flag | prereqs | _ancestors(cur, prereqs))


def _ancestors(cur, ids):
    by = {l["id"]: l for l in cur}
    out, todo = set(), list(ids)
    while todo:
        for p in by[todo.pop()]["prereqs"]:
            if p not in out:
                out.add(p)
                todo.append(p)
    return out


def test_journey_model_governance_rejects_impressive_noise(monkeypatch):
    """A researcher compares candidates; the best-looking one is rejected after corrections."""
    from tests.lab.test_hypothesis import panel

    p = panel(edge=0.0, seed=21)
    monkeypatch.setattr(api, "_panel", lambda src: (p, {"source": "synthetic", "warnings": [], "first": "2018-01-01", "last": "2020-12-31"}))
    c = _client(monkeypatch, make_data())
    base = {"program": "x = trades", "score": "x", "start": "2018-09-01", "end": "2020-09-30", "horizon": 5,
            "universe_n": 60, "min_names": 30, "holdout_months": 3, "permutations": 100}
    cands = [{"program": f"c{i} = mean(volume, {3 + i}) / mean(volume, 40)", "score": f"c{i}"} for i in range(5)]
    r = c.post("/lab/v1/hypothesis/compare", json={"base": base, "candidates": cands}, headers=KEY).json()
    assert r["status"] == "ok" and not r["best_survives_corrections"]
    assert r["in_sample_best"] in {x["score"] for x in cands}
