"""DB-19: watchlist rows (same Portfolio table) must never count as holdings."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd


def _make_user_with_holding_and_watchlist():
    """One holding bought a week ago and one watchlist row added a year ago."""
    import database
    from models.db_models import Portfolio, User

    holding_at = datetime.now() - timedelta(days=7)
    with database.get_session() as session:
        user = User(username=f"grp_{uuid4().hex[:12]}", password_hash="x", display_name="Group Test")
        session.add(user)
        session.flush()
        user_id = int(user.id)  # type: ignore[arg-type]
        session.add(Portfolio(
            user_id=user_id, ticker="HOLDX", company_name="Hold Ltd", shares=2, buy_price=100.0,
            group_name="holdings", created_at=holding_at,
        ))
        session.add(Portfolio(
            user_id=user_id, ticker="WATCHX", company_name="Watch Ltd", shares=0, buy_price=0.0,
            group_name="watchlist", created_at=datetime.now() - timedelta(days=365),
        ))
        session.commit()
    return user_id, holding_at, {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


def test_portfolio_default_group_is_holdings():
    import database
    from models.db_models import Portfolio, User

    with database.get_session() as session:
        user = User(username=f"grp_{uuid4().hex[:12]}", password_hash="x", display_name="Default Group")
        session.add(user)
        session.flush()
        row = Portfolio(user_id=user.id, ticker="DEFX", company_name="Def Ltd", shares=1, buy_price=10.0)
        session.add(row)
        session.commit()
        assert str(row.group_name) == "holdings"


def test_benchmark_uses_holding_inception(client, monkeypatch):
    import routers.portfolio_analytics as portfolio_router

    uid, holding_at, headers = _make_user_with_holding_and_watchlist()
    nifty = SimpleNamespace(history=lambda **_kw: pd.DataFrame({"Close": [20000.0, 20100.0]}))
    monkeypatch.setattr(portfolio_router.yf, "Ticker", lambda _sym: nifty)
    monkeypatch.setattr(portfolio_router, "_to_ns", lambda t: t)
    priced = []
    monkeypatch.setattr(portfolio_router, "_yf_price", lambda sym: (priced.append(sym), (110.0, 100.0))[1])

    r = client.get("/portfolio/benchmark", params={"user_id": uid}, headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["earliest_holding_date"] == holding_at.isoformat()
    assert body["period_days"] == 7
    assert body["current_portfolio_value"] == 220.0
    assert priced == ["HOLDX"]


def test_admin_export_counts_only_holdings(client, monkeypatch):
    import main

    monkeypatch.setattr(main, "require_admin", lambda _authorization=None: 1)
    uid, _, _ = _make_user_with_holding_and_watchlist()

    r = client.get("/dashboard-user-data", params={"user_id": uid})

    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["portfolio"]) == 2  # export keeps both rows, labelled
    assert body["portfolio_summary"] == {"total_invested": 200.0, "holdings_count": 1}
