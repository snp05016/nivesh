"""ARCH-11: one market-data gateway.

services/yfinance_client (and services/nse_client for NSE/index data) own the
rate limiter, circuit breaker and ticker resolution. Other modules re-export
from them instead of keeping their own copies, and direct yf.Ticker/yf.download
call sites may only shrink (ratchet).
"""
import importlib.util
import re
from pathlib import Path
from unittest.mock import MagicMock

import services.yfinance_client as yfc
from config.settings import NSE_TICKER_OVERRIDES

BACKEND = Path(__file__).resolve().parent.parent

# Gateway modules: allowed to call yfinance directly.
_GATEWAY = {"services/yfinance_client.py", "services/nse_client.py"}

# Direct call sites per file today. Lower a number (or drop the line) when a file
# migrates to the gateway; never raise one or add a file.
_YF_DIRECT_CALL_BASELINE = {
    "routers/analysis.py": 6,
    "routers/earnings.py": 2,
    "routers/market.py": 12,
    "routers/portfolio_analytics.py": 5,
    "scripts/populate_stock_universe.py": 1,
    "services/correlation_engine.py": 3,
    "services/extreme_enrichers.py": 3,
    "services/feedback_injector.py": 2,
    "services/market_service.py": 2,
    "services/math_engines/covariance.py": 1,
    "services/math_engines/currency_commodity.py": 1,
    "services/math_engines/vasicek.py": 3,
    "services/ml_signal_service.py": 1,
    "services/nse_data_provider.py": 4,
    "services/orchestrator.py": 5,
    "services/outcome_labels.py": 1,
    "services/piotroski.py": 1,
    "services/portfolio_service.py": 2,
    "services/portfolio_snapshot.py": 2,
    "services/scraper.py": 6,
    "services/sector_rotation.py": 4,
    "services/strategy_engine.py": 1,
    "services/youtube_harvester.py": 1,
}

_YF_CALL = re.compile(r"\b_?(?:yf|yfinance)\.(?:Ticker|Tickers|download)\(")


def _backend_py_files():
    yield from sorted(BACKEND.glob("*.py"))
    for d in ("services", "routers", "core", "repositories", "scripts"):
        yield from sorted((BACKEND / d).rglob("*.py"))


def _real_nse_data_provider():
    # conftest replaces services.nse_data_provider with a MagicMock; load the file.
    path = BACKEND / "services" / "nse_data_provider.py"
    spec = importlib.util.spec_from_file_location("_real_nse_data_provider", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_new_direct_yfinance_calls():
    counts = {}
    for path in _backend_py_files():
        rel = path.relative_to(BACKEND).as_posix()
        if rel in _GATEWAY:
            continue
        n = len(_YF_CALL.findall(path.read_text(encoding="utf-8")))
        if n:
            counts[rel] = n
    grown = {
        rel: (n, _YF_DIRECT_CALL_BASELINE.get(rel, 0))
        for rel, n in counts.items()
        if n > _YF_DIRECT_CALL_BASELINE.get(rel, 0)
    }
    assert grown == {}, (
        "new direct yfinance calls (file: (now, baseline)); use services.yfinance_client "
        f"helpers instead: {grown}"
    )


def test_ratchet_scan_sees_files():
    assert "orchestrator.py" in {p.name for p in _backend_py_files()}
    assert _YF_CALL.search("x = yf.Ticker(sym).info")
    assert _YF_CALL.search("import yfinance as _yf; _yf.download(t)")


def test_single_resolver(monkeypatch):
    ndp = _real_nse_data_provider()
    assert ndp.to_ns is yfc._to_ns
    assert ndp.resolve_ticker is yfc._resolve_ticker
    assert ndp.fetch_info is yfc._yf_fetch_info
    assert ndp.fetch_price is yfc._yf_price

    monkeypatch.setattr(yfc, "_resolve_with_fallback", lambda base, suffix: f"{base}{suffix}")
    assert NSE_TICKER_OVERRIDES
    for bare, symbol in NSE_TICKER_OVERRIDES.items():
        assert ndp.to_ns(bare) == yfc._to_ns(bare) == symbol


def test_yf_fetch_info_takes_rate_limit_token(monkeypatch):
    acquire = MagicMock()
    fake_yf = MagicMock()
    fake_yf.Ticker.return_value.info = {"currentPrice": 101.5}
    monkeypatch.setattr(yfc, "yf_acquire", acquire)
    monkeypatch.setattr(yfc, "yf", fake_yf)
    monkeypatch.setattr(yfc, "yf_circuit_is_open", lambda: False)

    assert yfc._yf_fetch_info("X.NS") == {"currentPrice": 101.5}
    acquire.assert_called()
    fake_yf.Ticker.assert_called_with("X.NS")


def test_duplicate_helpers_are_reexports():
    import services.market_service as market_service
    import services.nse_client as nse_client
    import services.portfolio_service as portfolio_service

    assert market_service._yf_fetch_info is yfc._yf_fetch_info
    assert portfolio_service._get_indices_data is nse_client._get_indices_data
    assert portfolio_service._INDICES_TICKERS is nse_client._INDICES_TICKERS
    assert portfolio_service._nse_session is nse_client._nse_session
    assert portfolio_service._get_asm_gsm_lists is nse_client._get_asm_gsm_lists
