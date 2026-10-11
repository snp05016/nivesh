"""CMKT-12: /earnings-calendar lists only the caller's holdings and needs a token.

It used to list the union of every user's holdings, unauthenticated, from one
global cache entry. Uses the conftest stub users (990001-990003).
"""
from datetime import date, timedelta

import pytest

import routers.earnings as earnings_router

CALLER, OTHER, SOLO = 990001, 990002, 990003
_TICKERS = ("ZZCALLER", "ZZOTHER", "ZZBAD", "ZZGOOD")


def _bearer(uid: int) -> dict:
    from database import create_access_token

    return {"Authorization": f"Bearer {create_access_token(uid)}"}


def _clear() -> None:
    from database import Portfolio, get_session

    with get_session() as session:
        session.query(Portfolio).filter(Portfolio.ticker.in_(_TICKERS)).delete(synchronize_session=False)
        session.commit()


@pytest.fixture
def holdings(monkeypatch):
    from database import Portfolio, get_session

    # Bypass the shared cache so each test computes from the DB.
    monkeypatch.setattr(earnings_router, "cached_call", lambda _ns, _key, fn, **_kw: fn())
    monkeypatch.setattr(earnings_router, "_resolve_ticker", lambda t, _ex: t)
    _clear()

    def _add(uid: int, ticker: str) -> None:
        with get_session() as session:
            session.add(Portfolio(user_id=uid, ticker=ticker, company_name=ticker, shares=1,
                                  buy_price=100.0, group_name="holdings"))
            session.commit()

    yield _add
    _clear()


def test_requires_auth(client):
    assert client.get("/earnings-calendar").status_code == 401


def test_only_callers_holdings(client, holdings, monkeypatch):
    holdings(CALLER, "ZZCALLER")
    holdings(OTHER, "ZZOTHER")
    monkeypatch.setattr(
        earnings_router, "_ticker_earnings_events",
        lambda t, _today: [{"ticker": t, "earnings_date": "01-Jan-2030", "days_away": 5}],
    )

    resp = client.get("/earnings-calendar", headers=_bearer(CALLER))

    assert resp.status_code == 200, resp.text
    assert [e["ticker"] for e in resp.json()["events"]] == ["ZZCALLER"]


def test_one_bad_ticker_does_not_500(client, holdings, monkeypatch):
    holdings(SOLO, "ZZBAD")
    holdings(SOLO, "ZZGOOD")
    upcoming = date.today() + timedelta(days=5)

    class _Ticker:
        def __init__(self, sym):
            self.sym = sym

        @property
        def calendar(self):
            if self.sym == "ZZBAD":
                raise RuntimeError("yahoo rate limited")
            return {"Earnings Date": [upcoming]}

    monkeypatch.setattr(earnings_router.yf, "Ticker", _Ticker)

    resp = client.get("/earnings-calendar", headers=_bearer(SOLO))

    assert resp.status_code == 200, resp.text
    events = resp.json()["events"]
    assert [(e["ticker"], e["days_away"]) for e in events] == [("ZZGOOD", 5)]


def test_all_lookups_failing_is_not_cached(monkeypatch):
    monkeypatch.setattr(earnings_router, "_holding_tickers", lambda _uid: ["ZZBAD"])
    monkeypatch.setattr(earnings_router, "_ticker_earnings_events", lambda _t, _today: None)
    seen = {}

    def _cached_call(_ns, key, fn, cache_if, **_kw):
        value = fn()
        seen[key] = cache_if(value)
        return value

    monkeypatch.setattr(earnings_router, "cached_call", _cached_call)

    assert earnings_router.earnings_calendar_endpoint(SOLO) == {"events": []}
    assert seen == {f"earnings_calendar_{SOLO}": False}
