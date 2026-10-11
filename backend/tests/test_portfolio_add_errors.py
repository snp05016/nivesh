"""POST /portfolio/add: ledger errors surface as 400s and purchase_date reaches the ledger (CMON-20, CMON-21)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest


@pytest.fixture(autouse=True)
def _no_live_price(monkeypatch):
    import routers.portfolio as portfolio_router

    monkeypatch.setattr(portfolio_router, "_yf_price", lambda *_a, **_k: (None, None))


def _user() -> tuple[int, dict]:
    import database
    from models.db_models import User

    with database.get_session() as session:
        user = User(username=f"add_err_{uuid4().hex[:12]}", password_hash="test", display_name="Add Errors")
        session.add(user)
        session.commit()
        session.refresh(user)
        uid = int(user.id)  # type: ignore[arg-type]
        return uid, {"Authorization": f"Bearer {database.create_access_token(uid)}"}


def _add(client, user_id: int, headers: dict, **overrides):
    body = {
        "user_id": user_id, "ticker": "RELIANCE", "company_name": "Reliance Industries",
        "shares": 10, "buy_price": 100.0, "transaction_type": "BUY",
    }
    body.update(overrides)
    return client.post("/portfolio/add", json=body, headers=headers)


def _ledger(user_id: int, ticker: str = "RELIANCE"):
    import database
    from models.db_models import Portfolio, Transaction

    with database.get_session() as session:
        txns = session.query(Transaction).filter_by(user_id=user_id, ticker=ticker).all()
        row = session.query(Portfolio).filter_by(user_id=user_id, ticker=ticker, group_name="holdings").first()
        return [(str(t.transaction_type), t.date) for t in txns], (str(row.purchase_date) if row else None)


def test_oversell_returns_400_with_detail(client):
    user_id, headers = _user()
    assert _add(client, user_id, headers).status_code == 200

    r = _add(client, user_id, headers, shares=20, transaction_type="SELL")

    assert r.status_code == 400
    assert r.json()["detail"].startswith("Cannot SELL")


def test_purchase_date_reaches_ledger(client):
    user_id, headers = _user()

    r = _add(client, user_id, headers, purchase_date="2023-05-02")

    assert r.status_code == 200
    txns, purchase_date = _ledger(user_id)
    assert [(t, d.date()) for t, d in txns] == [("BUY", date(2023, 5, 2))]
    assert purchase_date == "2023-05-02"


def test_legacy_purchase_date_format_accepted(client):
    user_id, headers = _user()

    r = _add(client, user_id, headers, purchase_date="02-May-2023")

    assert r.status_code == 200
    txns, purchase_date = _ledger(user_id)
    assert txns[0][1].date() == date(2023, 5, 2)
    assert purchase_date == "2023-05-02"


@pytest.mark.parametrize("bad", ["2023-13-45", "yesterday"])
def test_unparseable_purchase_date_400(client, bad):
    user_id, headers = _user()

    r = _add(client, user_id, headers, purchase_date=bad)

    assert r.status_code == 400
    assert _ledger(user_id)[0] == []


def test_future_purchase_date_400(client):
    user_id, headers = _user()
    future = (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%Y-%m-%d")

    r = _add(client, user_id, headers, purchase_date=future)

    assert r.status_code == 400
    assert "future" in r.json()["detail"]
