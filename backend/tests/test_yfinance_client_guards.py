"""REL-14: the shared yfinance wrappers are throttled, share one locked circuit
breaker, never cache a failed ticker resolution as resolved, and keep junk
ticker strings away from Yahoo. yfinance is a MagicMock (tests/conftest.py);
the autouse _reset_yf_guards fixture resets breaker state and both caches.
"""
from unittest.mock import MagicMock

import pandas as pd
import pytest

import services.yfinance_client as yfc


@pytest.fixture
def ticker(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(yfc.yf, "Ticker", mock)
    monkeypatch.setattr(yfc.time, "sleep", lambda *_a: None)
    return mock


def test_unresolved_not_cached_positive(ticker):
    type(ticker.return_value).fast_info = property(MagicMock(side_effect=RuntimeError("yahoo down")))

    assert yfc._resolve_with_fallback("ZZZQ", ".NS") == "ZZZQ.NS"
    assert "ZZZQ.NS" not in yfc._ticker_resolution_cache
    assert "ZZZQ.NS" in yfc._ticker_unresolved
    calls = ticker.call_count
    assert calls == 2  # preferred + fallback exchange

    assert yfc._resolve_with_fallback("ZZZQ", ".NS") == "ZZZQ.NS"
    assert ticker.call_count == calls  # negative-cached: no new probe


def test_resolved_cached(ticker):
    ticker.return_value.fast_info = MagicMock(last_price=10.0)

    assert yfc._resolve_with_fallback("TCS", ".NS") == "TCS.NS"
    assert yfc._ticker_resolution_cache["TCS.NS"] == "TCS.NS"
    yfc._resolve_with_fallback("TCS", ".NS")
    assert ticker.call_count == 1


def test_fallback_exchange_resolution_cached(ticker):
    def _for(sym):
        m = MagicMock()
        m.fast_info = MagicMock(last_price=None if sym.endswith(".NS") else 5.0)
        return m
    ticker.side_effect = _for

    assert yfc._resolve_with_fallback("BSEONLY", ".NS") == "BSEONLY.BO"
    assert yfc._ticker_resolution_cache["BSEONLY.NS"] == "BSEONLY.BO"


@pytest.mark.parametrize("junk", ["DROP TABLE;", "../../etc", "A" * 40, ""])
def test_invalid_syntax_no_network(ticker, junk):
    assert yfc._resolve_with_fallback(junk, ".NS") == f"{junk}.NS"
    ticker.assert_not_called()
    assert len(yfc._ticker_resolution_cache) == 0
    assert len(yfc._ticker_unresolved) == 0


@pytest.mark.parametrize("sym", ["M&M", "BAJAJ-AUTO", "TCS"])
def test_valid_symbols_pass_syntax_check(sym):
    assert yfc._TICKER_RE.match(sym)


def test_yf_acquire_called(ticker, monkeypatch):
    acquired = []
    monkeypatch.setattr(yfc, "yf_acquire", lambda: acquired.append(1))
    ticker.return_value.history.return_value = pd.DataFrame({"Close": [100.0, 101.0]})

    assert yfc._yf_price("X.NS") == (101.0, 100.0)
    assert len(acquired) == 1

    ticker.return_value.info = {"currentPrice": 5.0}
    yfc._yf_fetch_info("X.NS")
    assert len(acquired) == 2


def test_breaker_short_circuits(ticker, monkeypatch):
    monkeypatch.setattr(yfc, "_YF_CIRCUIT_THRESHOLD", 2)
    ticker.return_value.history.side_effect = RuntimeError("429")

    # One _yf_price makes two attempts -> two failures -> breaker opens.
    assert yfc._yf_price("X.NS") == (None, None)
    assert yfc.yf_circuit_is_open()
    calls = ticker.call_count

    assert yfc._yf_price("Y.NS") == (None, None)
    assert yfc._yf_fetch_info("Y.NS") == {}
    assert ticker.call_count == calls


def test_breaker_resets_on_success(ticker, monkeypatch):
    monkeypatch.setattr(yfc, "_YF_CIRCUIT_THRESHOLD", 3)
    yfc.yf_circuit_record_failure()
    yfc.yf_circuit_record_failure()
    ticker.return_value.history.return_value = pd.DataFrame({"Close": [1.0, 2.0]})
    yfc._yf_price("X.NS")
    yfc.yf_circuit_record_failure()
    assert not yfc.yf_circuit_is_open()


def test_resolution_probe_errors_do_not_trip_breaker(ticker, monkeypatch):
    monkeypatch.setattr(yfc, "_YF_CIRCUIT_THRESHOLD", 2)
    type(ticker.return_value).fast_info = property(MagicMock(side_effect=KeyError("junk")))

    for i in range(5):
        yfc._resolve_with_fallback(f"JUNK{i}", ".NS")
    assert not yfc.yf_circuit_is_open()


def test_analysis_uses_shared_breaker():
    import routers.analysis as analysis
    assert analysis._yf_circuit_is_open is yfc.yf_circuit_is_open
    assert analysis._yf_circuit_record_failure is yfc.yf_circuit_record_failure
    assert analysis._yf_circuit_record_success is yfc.yf_circuit_record_success
