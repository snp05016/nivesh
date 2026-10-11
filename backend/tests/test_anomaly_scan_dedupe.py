"""PERF-19: the anomaly scan upserts one row per (ticker, type, IST day), prunes
rows older than 30 days, passes NSE the bare option-chain symbol and no longer
downloads the bhavcopy."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest

import services.anomaly_scanner as scanner
from database import get_session
from models.db_models import MarketAnomaly

TICKERS = {"RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS"}


def _history(_ticker, period_days=365):
    n = 60
    close = [100.0 + (i % 2) for i in range(n)]  # alternating: no gap, no streak, no breakout
    volume = [1000.0] * (n - 1) + [6000.0]       # 6x the 20-day average -> VOLUME_SPIKE
    return pd.DataFrame({
        "Open": close,
        "High": [c + 1 for c in close],
        "Low": [c - 1 for c in close],
        "Close": close,
        "Volume": volume,
    }, index=pd.date_range("2026-01-01", periods=n, freq="D"))


def _count():
    with get_session() as db:
        return db.query(MarketAnomaly).filter(MarketAnomaly.ticker.in_(TICKERS.values())).count()


@pytest.fixture
def chain_mock(monkeypatch):
    with get_session() as db:
        db.query(MarketAnomaly).filter(MarketAnomaly.ticker.in_(TICKERS.values())).delete(
            synchronize_session=False)
        db.commit()
    chain = MagicMock(return_value=None)
    monkeypatch.setattr(scanner, "NSE_TICKERS", TICKERS)
    monkeypatch.setattr(scanner, "get_price_history", _history)
    monkeypatch.setattr(scanner, "fetch_info", lambda ticker: {})
    monkeypatch.setattr(scanner, "fetch_option_chain", chain)
    return chain


def test_rerun_no_duplicate_rows(chain_mock):
    first = scanner.run_anomaly_scan()
    assert any(a["anomaly_type"] == "VOLUME_SPIKE" for a in first)
    after_first = _count()
    assert after_first == len(first) > 0

    scanner.run_anomaly_scan()
    assert _count() == after_first


def test_retention_prunes_old_rows(chain_mock):
    with get_session() as db:
        db.add(MarketAnomaly(
            ticker="RELIANCE.NS", company="RELIANCE", anomaly_type="GAP_UP", severity="LOW",
            detail="old", price=1.0, change_pct=0.0,
            timestamp=datetime.now(timezone.utc) - timedelta(days=40),
        ))
        db.commit()

    scanner.run_anomaly_scan()

    with get_session() as db:
        assert db.query(MarketAnomaly).filter(MarketAnomaly.detail == "old").count() == 0


def test_option_chain_bare_symbol(chain_mock):
    scanner.run_anomaly_scan()
    symbols = {c.args[0] for c in chain_mock.call_args_list}
    assert symbols == {"RELIANCE", "TCS"}


def test_no_bhavcopy_download():
    assert not hasattr(scanner, "download_bhavcopy")


def test_latest_anomalies_survive_weekend():
    """The scan runs Mon-Fri only: Friday's rows must still be served ~40 h later."""
    now = datetime.now(timezone.utc)
    with get_session() as db:
        db.query(MarketAnomaly).delete(synchronize_session=False)
        for detail, age in (("friday", 40), ("thursday", 70)):
            db.add(MarketAnomaly(
                ticker="RELIANCE.NS", company="RELIANCE", anomaly_type="VOLUME_SPIKE",
                severity="HIGH", detail=detail, price=1.0, change_pct=0.0,
                timestamp=now - timedelta(hours=age),
            ))
        db.commit()

    assert [a["detail"] for a in scanner.get_latest_anomalies()] == ["friday"]
