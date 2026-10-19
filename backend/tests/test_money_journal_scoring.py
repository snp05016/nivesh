"""C16: journal entries scored against the Nifty 50, in a background task after the GET."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import database
from models.db_models import TradeJournal, User
from services import money_journal_scoring as mjs
from services import money_market_series as mms


def _user():
    uid = random.randint(70_000_000, 79_999_999)
    with database.get_session() as session:
        session.add(User(id=uid, username=f"jscore_{uid}", password_hash="x", display_name="J"))
        session.commit()
    return uid, {"Authorization": f"Bearer {database.create_access_token(uid)}"}


def _entry(uid, action="BUY", ticker="INFY", days_ago=200, market_score=None):
    with database.get_session() as session:
        row = TradeJournal(user_id=uid, ticker=ticker, action=action, price_at_time=100.0, reason_text="r",
                           created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago),
                           market_score=market_score)
        session.add(row)
        session.commit()
        return int(row.id)


def _scores(entry_id):
    with database.get_session() as session:
        return session.get(TradeJournal, entry_id).market_score


@pytest.fixture(autouse=True)
def env(monkeypatch):
    mjs._last_run.clear()
    mjs._last_result.clear()
    monkeypatch.setattr(mjs, "is_enabled", lambda key: True)
    monkeypatch.setattr(mms, "display_allowed", lambda: True)
    calls = []

    def fake(items):
        calls.append(items)
        return {i["key"]: {"key": i["key"], "status": "ok", "return_pct": 3.2, "nifty_return_pct": 1.1,
                           "start_date": "2024-03-05", "end_date": "2024-04-04", "stale_exit": False} for i in items}

    monkeypatch.setattr(mms, "window_returns", fake)
    return calls


def test_buy_and_sell_decision_excess(env):
    uid, _ = _user()
    buy, sell = _entry(uid, "BUY"), _entry(uid, "SELL")
    assert mjs.score_pending(uid) == 4
    assert _scores(buy)["21"]["decision_excess_pp"] == 2.1
    assert _scores(buy)["21"]["stock_pct"] == 3.2 and _scores(buy)["21"]["nifty_pct"] == 1.1
    assert _scores(sell)["63"]["decision_excess_pp"] == -2.1
    assert _scores(sell)["63"]["excess_pp"] == 2.1


def test_young_entry_pending_not_stored(env):
    uid, _ = _user()
    young = _entry(uid, "BUY", days_ago=10)
    assert mjs.score_pending(uid) == 0
    assert env == [] and _scores(young) is None
    block = mjs.market_block(_rows(uid), True, None)
    assert block["horizons"][0]["pending"] == 1 and block["horizons"][0]["scored"] == 0


def _rows(uid):
    with database.get_session() as session:
        return [SimpleNamespace(id=r.id, action=r.action, market_score=r.market_score)
                for r in session.query(TradeJournal).filter_by(user_id=uid).all()]


def test_final_entry_never_overwritten(env):
    uid, _ = _user()
    keep = {"21": {"status": "ok", "stock_pct": 9.0, "nifty_pct": 1.0, "excess_pp": 8.0, "decision_excess_pp": 8.0}}
    eid = _entry(uid, "BUY", market_score=keep)
    mjs.score_pending(uid)
    assert _scores(eid)["21"]["stock_pct"] == 9.0
    assert _scores(eid)["63"]["status"] == "ok"
    assert all(i["key"] != f"j{eid}:21" for batch in env for i in batch)


def test_hold_and_watch_untouched(env):
    uid, _ = _user()
    hold, watch = _entry(uid, "HOLD"), _entry(uid, "WATCH")
    assert mjs.score_pending(uid) == 0
    assert env == [] and _scores(hold) is None and _scores(watch) is None


def test_flag_off_and_display_gate(env, monkeypatch):
    uid, _ = _user()
    eid = _entry(uid)
    monkeypatch.setattr(mjs, "is_enabled", lambda key: False)
    assert mjs.score_pending(uid) == 0 and env == []
    assert mjs.market_status(uid, _rows(uid)) == (False, "flag_off")
    monkeypatch.setattr(mjs, "is_enabled", lambda key: True)
    monkeypatch.setattr(mms, "display_allowed", lambda: False)
    assert mjs.score_pending(uid) == 0 and env == []
    assert mjs.market_status(uid, _rows(uid)) == (False, "engine_not_live")
    block = mjs.market_block(_rows(uid), False, "engine_not_live")
    assert block["available"] is False and block["entries"] == {} and block["reason"] == "engine_not_live"
    assert _scores(eid) is None


def test_engine_none_writes_nothing_and_marks_unreachable(env, monkeypatch):
    uid, _ = _user()
    eid = _entry(uid)
    monkeypatch.setattr(mms, "window_returns", lambda items: None)
    assert mjs.score_pending(uid) == 0
    assert _scores(eid) is None
    assert mjs.market_status(uid, _rows(uid)) == (False, "engine_unreachable")


def test_throttle_blocks_second_run(env):
    uid, _ = _user()
    _entry(uid)
    assert mjs.score_pending(uid) == 2
    _entry(uid)
    assert mjs.score_pending(uid) == 0
    assert len(env) == 1


def test_other_users_entries_not_scored(env):
    uid, _ = _user()
    other, _ = _user()
    theirs = _entry(other)
    _entry(uid)
    mjs.score_pending(uid)
    assert _scores(theirs) is None
    assert all(i["key"] != f"j{theirs}:21" for batch in env for i in batch)


def test_market_block_stats():
    ok = lambda d: {"status": "ok", "decision_excess_pp": d, "end_date": "2024-04-04"}  # noqa: E731
    rows = [
        SimpleNamespace(id=1, action="BUY", market_score={"21": ok(2.0)}),
        SimpleNamespace(id=2, action="BUY", market_score={"21": ok(-1.0)}),
        SimpleNamespace(id=3, action="SELL", market_score={"21": ok(-0.8)}),
        SimpleNamespace(id=4, action="BUY", market_score=None),
        SimpleNamespace(id=5, action="HOLD", market_score=None),
    ]
    block = mjs.market_block(rows, True, None)
    h21 = block["horizons"][0]
    assert block["available"] and block["as_of"] == "2024-04-04"
    assert (h21["scored"], h21["pending"], h21["favourable"]) == (3, 1, 1)
    assert h21["by_action"]["BUY"] == {"scored": 2, "favourable": 1, "median_decision_excess_pp": 0.5}
    assert h21["by_action"]["SELL"]["favourable"] == 0
    assert set(block["entries"]) == {"1", "2", "3"}


def test_get_does_not_wait_for_scoring(client, env, monkeypatch):
    uid, headers = _user()
    eid = _entry(uid)
    spy = []
    monkeypatch.setattr(mjs, "score_pending", lambda user_id, limit=200: spy.append(user_id) or 0)
    response = client.get(f"/trade-journal/{uid}/stats", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["market"]["available"] is True
    assert body["market"]["horizons"][0]["pending"] == 1
    assert _scores(eid) is None  # the GET itself wrote nothing
    # TestClient runs background tasks after the response; the spy proves it went through BackgroundTasks.
    assert spy == [uid]
