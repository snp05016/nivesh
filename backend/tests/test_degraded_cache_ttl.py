"""PERF-18: failed or partial upstream results must not be cached for the full TTL."""
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

import services.nse_client as nse_client
import services.scraper as scraper
from config.settings import ASM_GSM_CACHE_TTL
from routers import market


class _Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, namespace, key, value, ttl=None):
        self.calls.append((namespace, key, value, ttl))


# ── top movers ───────────────────────────────────────────────────────────────

def _movers_frame():
    cols = {}
    for sym in ("RELIANCE.NS", "TCS.NS"):
        cols[(sym, "Close")] = [100.0, 102.0]
        cols[(sym, "Volume")] = [1000.0, 1500.0]
    return pd.DataFrame(cols)  # tuple keys -> MultiIndex, like yf group_by="ticker"


@pytest.fixture
def movers_cache(monkeypatch):
    dc = sys.modules["services.disk_cache"]
    rec = _Recorder()
    monkeypatch.setattr(dc, "get", lambda namespace, key: None)
    monkeypatch.setattr(dc, "set", rec)
    return rec


def test_top_movers_empty_ttl_60(monkeypatch, movers_cache):
    monkeypatch.setattr(market, "yf", SimpleNamespace(download=lambda *a, **k: pd.DataFrame()))
    result = market.top_movers_endpoint()
    assert result["gainers"] == []
    assert [c[3] for c in movers_cache.calls] == [60]


def test_top_movers_success_ttl_900(monkeypatch, movers_cache):
    monkeypatch.setattr(market, "yf", SimpleNamespace(download=lambda *a, **k: _movers_frame()))
    result = market.top_movers_endpoint()
    assert {m["ticker"] for m in result["gainers"]} == {"RELIANCE", "TCS"}
    assert [c[3] for c in movers_cache.calls] == [900]


# ── stock profile ────────────────────────────────────────────────────────────

def _boom(*_a, **_k):
    raise RuntimeError("upstream down")


def test_stock_profile_partial_ttl(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(market, "_dcache_get", lambda namespace, key: None)
    monkeypatch.setattr(market, "_dcache_set", rec)
    monkeypatch.setattr(market, "_resolve_ticker", lambda t, e: f"{t}.NS")
    monkeypatch.setattr(market, "_yf_fetch_info", lambda t: {})
    monkeypatch.setattr(market, "get_fundamentals", lambda t, e: {})
    monkeypatch.setattr(market, "get_price_history", _boom)
    monkeypatch.setattr(market, "_get_quarterly_fin", _boom)

    result = market.stock_profile_endpoint("ZZPERF18", "NSE")

    assert result["errors"]
    assert len(rec.calls) == 1 and rec.calls[0][3] == 60


# ── ASM / GSM lists ──────────────────────────────────────────────────────────

class _Resp:
    def __init__(self, status, symbols=()):
        self.status_code = status
        self._symbols = symbols

    def json(self):
        return {"data": [{"symbol": s} for s in self._symbols]}


def _asm_setup(monkeypatch, responses):
    rec = _Recorder()
    session = SimpleNamespace(get=lambda url, timeout=None: responses.pop(0))
    monkeypatch.setattr(nse_client, "_dcache_get", lambda namespace, key: None)
    monkeypatch.setattr(nse_client, "_dcache_set", rec)
    monkeypatch.setattr(nse_client, "_nse_session", lambda: session)
    return rec


def test_asm_gsm_non200_short_ttl(monkeypatch):
    rec = _asm_setup(monkeypatch, [_Resp(503), _Resp(503), _Resp(503)])
    data = nse_client._get_asm_gsm_lists()
    assert data == {"ASM": set(), "GSM": set()}
    assert rec.calls[0][3] == 120


def test_asm_gsm_partial_short_ttl(monkeypatch):
    rec = _asm_setup(monkeypatch, [_Resp(200, ["AAA"]), _Resp(503), _Resp(200, ["GGG"])])
    data = nse_client._get_asm_gsm_lists()
    assert data == {"ASM": {"AAA"}, "GSM": {"GGG"}}
    assert rec.calls[0][3] == 120


def test_asm_gsm_exception_short_ttl(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(nse_client, "_dcache_get", lambda namespace, key: None)
    monkeypatch.setattr(nse_client, "_dcache_set", rec)
    monkeypatch.setattr(nse_client, "_nse_session", _boom)
    nse_client._get_asm_gsm_lists()
    assert rec.calls[0][3] == 120


def test_asm_gsm_all_ok_full_ttl(monkeypatch):
    rec = _asm_setup(monkeypatch, [_Resp(200, ["AAA"]), _Resp(200, ["BBB"]), _Resp(200, ["GGG"])])
    data = nse_client._get_asm_gsm_lists()
    assert data == {"ASM": {"AAA", "BBB"}, "GSM": {"GGG"}}
    assert rec.calls[0][2] == {"ASM": ["AAA", "BBB"], "GSM": ["GGG"]}
    assert rec.calls[0][3] == ASM_GSM_CACHE_TTL


# ── market pulse ─────────────────────────────────────────────────────────────

@pytest.fixture
def clean_pulse_cache(monkeypatch):
    scraper._CACHE.clear()
    monkeypatch.setattr(scraper, "_firecrawl_extract", lambda url, schema: None)
    yield
    scraper._CACHE.clear()


def test_market_pulse_fallback_not_cached(monkeypatch, clean_pulse_cache):
    monkeypatch.setattr(scraper, "_fetch_pulse_fallback", lambda: {"indices": [], "advances": 0})
    assert scraper.fetch_market_pulse()["indices"] == []
    assert scraper._CACHE.get("market_pulse") is None


def test_market_pulse_fallback_with_indices_cached(monkeypatch, clean_pulse_cache):
    payload = {"indices": [{"name": "NIFTY 50"}], "advances": 10}
    monkeypatch.setattr(scraper, "_fetch_pulse_fallback", lambda: payload)
    assert scraper.fetch_market_pulse() == payload
    assert scraper._CACHE.get("market_pulse") == payload
