"""PERF-08: AnalysisHistory reads stop dragging the raw_output transcript and stop
running one query per ticker.

raw_output is a deferred column, the cache lookups return it only on request,
and latest_per_ticker answers "newest n rows per ticker" in one windowed query.
Repository tests use a private in-memory SQLite; the endpoint test uses the
conftest app and its temp test database.
"""
import json
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from models.db_models import AnalysisHistory, Base, User
from repositories.analysis_repo import (
    get_all_ticker_history,
    get_analysis_for_date,
    latest_per_ticker,
)

_BLOB = "x" * 100_000  # a 100 KB transcript
_TICKERS = [f"T{i}" for i in range(10)]
_SIGNALS = ["BULLISH", "BEARISH", "HOLD"]


def _seed(session, user_id):
    """10 tickers x 20 analyses, one day apart; run i of each ticker has signal _SIGNALS[i % 3]."""
    start = datetime(2026, 1, 1, 10, 0, 0)
    for t in _TICKERS:
        for i in range(20):
            created = start + timedelta(days=i)
            session.add(AnalysisHistory(
                user_id=user_id, ticker=t, analysis_date=created.date().isoformat(),
                signal=_SIGNALS[i % 3], full_json=json.dumps({"signal": _SIGNALS[i % 3], "n": i}),
                raw_output=f"{t}-{i}-{_BLOB}", scan_type="standard", created_at=created,
            ))
    session.commit()


@pytest.fixture()
def seeded():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    user = User(username="perf08_user", password_hash="hash", display_name="Perf User")
    session.add(user)
    session.commit()
    _seed(session, user.id)
    session.expunge_all()

    statements: list[str] = []

    def _collect(_conn, _cursor, statement, _params, _ctx, _many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _collect)
    try:
        yield session, statements
    finally:
        event.remove(engine, "before_cursor_execute", _collect)
        session.close()
        engine.dispose()


def test_raw_output_not_selected(seeded):
    session, statements = seeded
    rows = session.query(AnalysisHistory).all()
    assert len(rows) == 200
    assert len(statements) == 1
    assert "raw_output" not in statements[0]
    assert "full_json" in statements[0]

    # Still readable on demand, with one extra SELECT for that row only.
    assert rows[0].raw_output.startswith(f"{rows[0].ticker}-")
    assert len(statements) == 2


def test_latest_per_ticker(seeded):
    session, statements = seeded

    latest = latest_per_ticker(session, _TICKERS)

    assert len(statements) == 1
    assert "raw_output" not in statements[0] and "full_json" not in statements[0]
    assert set(latest) == set(_TICKERS)
    for rows in latest.values():
        assert len(rows) == 1
        assert rows[0].signal == _SIGNALS[19 % 3]  # run 19 is the newest
        assert rows[0].created_at == datetime(2026, 1, 20, 10, 0, 0)

    statements.clear()
    four = latest_per_ticker(session, _TICKERS[:3], n=4, cols=(AnalysisHistory.full_json,))
    assert len(statements) == 1
    assert set(four) == set(_TICKERS[:3])
    for rows in four.values():
        assert [json.loads(r.full_json)["n"] for r in rows] == [19, 18, 17, 16]  # newest first


def test_latest_per_ticker_filters(seeded):
    session, _ = seeded
    assert latest_per_ticker(session, []) == {}
    assert latest_per_ticker(session, ["T0"], user_id=-1) == {}
    # tickers=None scans all tickers; date_from bounds the window.
    recent = latest_per_ticker(session, None, n=50, date_from="2026-01-19")
    assert set(recent) == set(_TICKERS)
    assert all(len(rows) == 2 for rows in recent.values())


def test_cache_hit_excludes_raw_output(seeded):
    session, _ = seeded

    res = get_analysis_for_date(session, "T0", "", "standard")
    assert res is not None and res["n"] == 19
    assert "raw_output" not in res

    with_raw = get_analysis_for_date(session, "T0", "", "standard", include_raw=True)
    assert with_raw is not None
    assert with_raw["raw_output"].startswith("T0-19-")

    history = get_all_ticker_history(session, "T0")
    assert [h["n"] for h in history] == list(range(20))
    assert all("raw_output" not in h for h in history[:-1])
    assert history[-1]["raw_output"].startswith("T0-19-")  # smart-cache reuse keeps the newest transcript


def test_portfolio_endpoint_query_budget(client, monkeypatch):
    import database
    import routers.portfolio as portfolio_router
    from models.db_models import Portfolio

    with database.get_session() as session:
        user = User(username=f"perf08_{uuid4().hex[:12]}", password_hash="x", display_name="Perf08")
        session.add(user)
        session.flush()
        uid = int(user.id)  # type: ignore[arg-type]
        for t in _TICKERS:
            session.add(Portfolio(user_id=uid, ticker=t, company_name=f"{t} Ltd",
                                  shares=1, buy_price=100.0, group_name="holdings"))
        session.commit()
        _seed(session, uid)
    headers = {"Authorization": f"Bearer {database.create_access_token(uid)}"}

    monkeypatch.setattr(portfolio_router, "_to_ns", lambda t: t)
    monkeypatch.setattr(portfolio_router, "_yf_price_with_status",
                        lambda sym: (110.0, 100.0, "live", None))

    statements: list[str] = []

    def _collect(_conn, _cursor, statement, _params, _ctx, _many):
        if "analysis_history" in statement:
            statements.append(statement)

    event.listen(database.ENGINE, "before_cursor_execute", _collect)
    try:
        r = client.get(f"/portfolio/{uid}", headers=headers)
    finally:
        event.remove(database.ENGINE, "before_cursor_execute", _collect)

    assert r.status_code == 200, r.text
    assert len(r.json()["holdings"]) == 10
    assert 1 <= len(statements) <= 3
    assert not any("raw_output" in s or "full_json" in s for s in statements)
