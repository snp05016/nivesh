"""I35: COVID-2020 replay of current stocks from the engine's history (no network)."""
from __future__ import annotations

from uuid import uuid4

import pytest

import database
from models.db_models import Portfolio, User
from services import disk_cache, money_crisis_replay, money_market_series as mms, money_pricing

END = "2020-03-23"


def _user():
    with database.get_session() as session:
        user = User(username=f"replay_{uuid4().hex[:12]}", password_hash="x", display_name="Replay")
        session.add(user)
        session.commit()
        uid = int(user.id)
    return uid, {"Authorization": f"Bearer {database.create_access_token(uid)}"}


def _hold(uid, ticker, shares, ac="EQ", name=None):
    with database.get_session() as session:
        session.add(Portfolio(user_id=uid, ticker=ticker, company_name=name or f"{ticker} Ltd", shares=shares, buy_price=1.0,
                              group_name="holdings", asset_class=ac))
        session.commit()


def _ok(key, ret, nifty=-37.4, end=END, stale=False):
    return {"key": key, "status": "ok", "return_pct": ret, "nifty_return_pct": nifty, "end_date": end, "stale_exit": stale}


@pytest.fixture
def world(monkeypatch):
    monkeypatch.setenv("FEATURE_MONEY_CRISIS_REPLAY", "true")
    cache = {}
    monkeypatch.setattr(disk_cache, "get", lambda ns, key: cache.get((ns, key)))
    monkeypatch.setattr(disk_cache, "set", lambda ns, key, value, ttl=None: cache.__setitem__((ns, key), value))
    state = {"allowed": True, "prices": {"AAA": 100.0, "BBB": 200.0}, "results": {}, "calls": [], "none": False}

    monkeypatch.setattr(mms, "display_allowed", lambda: state["allowed"])
    monkeypatch.setattr(money_pricing, "price_quotes",
                        lambda rows: {t: (money_pricing.PriceQuote(state["prices"][t], None, "live", None) if t in state["prices"]
                                          else money_pricing.UNAVAILABLE) for t, _ in rows})

    def window_returns(items):
        state["calls"].append(items)
        if state["none"]:
            return None
        return {i["key"]: state["results"][i["key"]] for i in items if i["key"] in state["results"]}

    monkeypatch.setattr(mms, "window_returns", window_returns)
    return state


def _get(client, headers, scenario="covid_2020"):
    return client.get(f"/api/v1/me/portfolio/crisis-replay?scenario={scenario}", headers=headers)


def test_weighted_return_and_rupee_change(client, world):
    uid, headers = _user()
    _hold(uid, "AAA", 10)   # value 1000, -30%
    _hold(uid, "BBB", 10)   # value 2000, -40%
    world["results"] = {"AAA": _ok("AAA", -30.0), "BBB": _ok("BBB", -40.0)}
    r = _get(client, headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["scenario"] == {"id": "covid_2020", "label": "COVID crash", "start": "2020-02-19", "end": END}
    assert body["nifty_return_pct"] == -37.4
    assert body["covered_value_inr"] == 3000.0
    assert body["portfolio_change_inr"] == -1100.0               # 1000 * -0.30 + 2000 * -0.40
    assert body["portfolio_return_pct"] == -36.7                 # -1100 / 3000
    assert [(h["ticker"], h["value_inr"], h["return_pct"]) for h in body["holdings"]] == [("AAA", 1000.0, -30.0), ("BBB", 2000.0, -40.0)]
    assert body["not_included"] == []
    assert body["notes"] == [
        "This replays how today's holdings moved in that window. It is not a forecast.",
        "Holdings not listed on 19 Feb 2020, mutual funds and holdings without a price are not included.",
        "Only stocks that still trade today are in your portfolio, so the replay can look better than what investors lived through.",
    ]
    assert world["calls"][0][0] == {"key": "AAA", "symbol": "AAA", "start": money_crisis_replay.SCENARIOS["covid_2020"]["start"], "sessions": 21}


def test_exclusions_get_no_return(client, world):
    uid, headers = _user()
    for t in ("AAA", "NEW", "GONE", "ZZZ"):
        _hold(uid, t, 10)
    _hold(uid, "INF179K01VC4", 100, "MF", "HDFC Flexi Cap")
    world["prices"].update({"NEW": 50.0, "GONE": 20.0, "INF179K01VC4": 40.0})
    world["results"] = {
        "AAA": _ok("AAA", -30.0),
        "NEW": {"key": "NEW", "status": "no_data"},
        "GONE": _ok("GONE", -90.0, stale=True),
    }
    body = _get(client, headers).json()
    assert [h["ticker"] for h in body["holdings"]] == ["AAA"]
    reasons = {n["ticker"]: n["reason"] for n in body["not_included"]}
    assert reasons == {"NEW": "listed_after_window", "GONE": "not_traded_at_window_end", "ZZZ": "unpriced",
                       "INF179K01VC4": "mutual_fund"}
    assert body["covered_value_inr"] == 1000.0 and body["portfolio_return_pct"] == -30.0
    # funds and unpriced stocks never reach the engine
    assert {i["key"] for i in world["calls"][0]} == {"AAA", "NEW", "GONE"}
    unpriced = next(n for n in body["not_included"] if n["ticker"] == "ZZZ")
    assert unpriced["value_inr"] is None


def test_calendar_mismatch_is_503(client, world):
    uid, headers = _user()
    _hold(uid, "AAA", 10)
    world["results"] = {"AAA": _ok("AAA", -30.0, end="2020-03-24")}
    r = _get(client, headers)
    assert r.status_code == 503 and r.json()["detail"]["code"] == "REPLAY_UNAVAILABLE"
    assert r.headers["Retry-After"] == "300"


def test_engine_unreachable_or_not_live_is_503(client, world):
    uid, headers = _user()
    _hold(uid, "AAA", 10)
    world["none"] = True
    assert _get(client, headers).status_code == 503
    world["none"] = False
    world["allowed"] = False
    world["calls"].clear()
    assert _get(client, headers).status_code == 503
    assert world["calls"] == []


def test_no_index_return_is_503(client, world):
    uid, headers = _user()
    _hold(uid, "NEW", 10)
    world["prices"]["NEW"] = 50.0
    world["results"] = {"NEW": {"key": "NEW", "status": "no_data"}}
    assert _get(client, headers).status_code == 503


def test_unknown_scenario_is_422(client, world):
    _, headers = _user()
    r = _get(client, headers, "dotcom_2000")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "UNKNOWN_SCENARIO"


def test_flag_off_is_404(client, world, monkeypatch):
    monkeypatch.delenv("FEATURE_MONEY_CRISIS_REPLAY", raising=False)
    _, headers = _user()
    r = _get(client, headers)
    assert r.status_code == 404 and r.json()["detail"]["code"] == "FEATURE_DISABLED"


def test_requires_auth(client, world):
    assert client.get("/api/v1/me/portfolio/crisis-replay").status_code == 401


def test_second_call_is_served_from_cache(client, world):
    uid, headers = _user()
    _hold(uid, "AAA", 10)
    world["results"] = {"AAA": _ok("AAA", -30.0)}
    first = _get(client, headers).json()
    second = _get(client, headers).json()
    assert first == second and len(world["calls"]) == 1
    _hold(uid, "BBB", 5)    # holdings changed: a fresh key
    world["results"]["BBB"] = _ok("BBB", -20.0)
    _get(client, headers)
    assert len(world["calls"]) == 2
