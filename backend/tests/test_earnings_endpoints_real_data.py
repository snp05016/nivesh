"""CMKT-01: the earnings endpoints never present AI analyses as results.

Feed rows are a tracked large cap's latest quarter against the same quarter a year
earlier (yfinance quarterly financials); the calendar and post-result movers use
yfinance earnings dates. An AnalysisHistory row is never read as a result.
"""
import json
from datetime import date, datetime, timezone

import pandas as pd
import pytest

import routers.earnings as earnings_router
from database import AnalysisHistory, get_session
from services import market_service


@pytest.fixture
def analysed_today():
    """A TCS AI analysis dated today with the fundamentals keys the old feed read."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with get_session() as session:
        row = AnalysisHistory(
            ticker="TCS", analysis_date=today, signal="BULLISH", confidence_pct=70,
            full_json=json.dumps({
                "company_name": "Tata Consultancy Services",
                "fundamentals_snapshot": {"revenue": 100.0, "net_profit": 50.0},
            }),
        )
        session.add(row)
        session.commit()
        row_id = row.id
    yield today
    with get_session() as session:
        session.query(AnalysisHistory).filter(AnalysisHistory.id == row_id).delete()
        session.commit()


def _fin(periods: list[str], revenue: list[float], profit: list[float]) -> pd.DataFrame:
    """A yfinance-shaped quarterly_financials frame (newest column first, raw rupees)."""
    return pd.DataFrame([revenue, profit], index=["Total Revenue", "Net Income"],
                        columns=pd.to_datetime(periods))


def test_feed_never_uses_analysis_history(client, analysed_today, monkeypatch):
    monkeypatch.setattr(market_service, "build_quarterly_earnings", lambda tickers: ([], "none"))

    resp = client.get("/api/v1/earnings/feed")

    assert resp.status_code == 200
    body = resp.json()
    assert body["results"] == [] and body["count"] == 0
    assert body["data_source"] == "empty"
    assert not any(r.get("revenue_prev") == 85.0 for r in body["latest"])


def test_feed_yoy_requires_prior_year_column(monkeypatch):
    four = _fin(["2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30"],
                [5e10, 4.8e10, 4.7e10, 4.6e10], [1e10, 9e9, 9e9, 8e9])
    monkeypatch.setattr(market_service, "_yf_fetch_info", lambda sym: {})
    monkeypatch.setattr(market_service, "_get_quarterly_fin", lambda sym: (None, four))

    results, diagnostic = market_service.build_quarterly_earnings(["TCS"])

    assert results == []  # no same quarter last year: left out, never estimated
    assert "same-quarter-last-year" in diagnostic

    five = _fin(["2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30", "2025-06-30"],
                [5e10, 4.8e10, 4.7e10, 4.6e10, 4e10], [1e10, 9e9, 9e9, 8e9, 8e9])
    monkeypatch.setattr(market_service, "_get_quarterly_fin", lambda sym: (None, five))
    monkeypatch.setattr(market_service, "_yf_fetch_info", lambda sym: {
        "longName": "Tata Consultancy Services Ltd", "regularMarketPrice": 4100.0, "previousClose": 4000.0,
    })

    (row,), diagnostic = market_service.build_quarterly_earnings(["TCS"])

    assert diagnostic == ""
    assert (row["revenue"], row["revenue_prev"]) == (5000.0, 4000.0)
    assert row["revenue_growth_pct"] == round((5000.0 - 4000.0) / 4000.0 * 100, 2)
    assert row["net_profit_growth_pct"] == 25.0
    assert row["quarter"] == "Q1 FY27"
    assert row["result_date"] == "2026-06-30"
    assert (row["ltp"], row["change_percent"]) == (4100.0, 2.5)


def test_progress_ignores_analysis_rows(client, analysed_today):
    resp = client.get("/api/v1/earnings/progress")

    assert resp.status_code == 503  # FAKE-08: no results-filing source, so no count
    assert "reported" not in resp.text


def test_calendar_ignores_analysis_rows(client, analysed_today, monkeypatch):
    scanned = []

    def _scan(target_date, tickers=None):
        scanned.append((target_date, tickers))
        return []

    monkeypatch.setattr(earnings_router, "_scan_upcoming_earnings", _scan)

    resp = client.get("/api/v1/earnings/calendar", params={"date": analysed_today})
    assert resp.status_code == 200
    assert resp.json()["results"] == [] and resp.json()["count"] == 0

    client.get("/api/v1/earnings/calendar", params={"date": analysed_today, "ticker": "tcs"})
    assert scanned == [(analysed_today, None), (analysed_today, ["TCS"])]


def test_post_result_movers_ignore_analysis_rows(client, analysed_today, monkeypatch):
    monkeypatch.setattr(market_service, "post_result_movers", lambda tickers: [])

    resp = client.get("/api/v1/earnings/post-result-movers")

    assert resp.status_code == 200
    assert resp.json()["movers"] == []


def test_post_result_move_is_measured_from_the_announcement(monkeypatch):
    announced = pd.to_datetime(["2026-10-15", "2026-07-15"]).tz_localize("Asia/Kolkata")
    days = pd.to_datetime(["2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"]).tz_localize("Asia/Kolkata")
    frames = {"earnings_dates": pd.DataFrame({"Reported EPS": [1.0, 1.0]}, index=announced)}
    monkeypatch.setattr(market_service, "_yf_frame", lambda sym, attr: frames.get(attr))
    monkeypatch.setattr(market_service, "yf_history", lambda sym, period: pd.DataFrame(
        {"Close": [100.0, 100.0, 104.0, 110.0], "Volume": [10, 20, 30, 40]}, index=days))
    monkeypatch.setattr(market_service, "_yf_price", lambda sym: (112.0, 110.0))

    move = market_service._post_result_move("TCS", date(2026, 10, 19))

    assert move is not None
    assert move["result_date"] == "2026-10-15"
    assert move["change_percent"] == 12.0  # live price against the 14 Oct pre-result close
    assert (move["ltp"], move["volume"]) == (112.0, 40)
    assert market_service._post_result_move("TCS", date(2026, 11, 30)) is None  # 46 days on
