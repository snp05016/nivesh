"""Decode-contract test for extreme analyses — proves a cached extreme payload
satisfies the iOS StockAnalysis Codable contract WITHOUT running any LLM (no credits).

Two layers:
  * Raw-shape tests run anywhere (they only read the committed fixture).
  * The normalization test imports services.orchestrator, which pulls in the heavy
    tradingagents stack; it is importorskip-guarded so it runs on the server (and
    any full-deps env) but skips cleanly on a thin local checkout.
"""
import json
import os

import pytest

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "extreme_reliance.json")


def _load():
    with open(FIXTURE) as f:
        return json.load(f)


def _assert_ios_contract(r):
    """Mirrors the non-optional fields in iOS StockAnalysis.init(from:)."""
    assert isinstance(r["ticker"], str)
    assert isinstance(r["company_name"], str)
    assert isinstance(r["analysis_date"], str)
    assert isinstance(r["signal"], str)
    assert isinstance(r["confidence_pct"], int) and 0 <= r["confidence_pct"] <= 100
    assert isinstance(r["current_price_inr"], (int, float))
    for k in ("short_term_3m", "medium_term_12m", "long_term_36m"):
        assert isinstance(r["target_prices"][k], (int, float))
    for k in ("short_term", "medium_term", "long_term"):
        assert k in r["upside_downside_pct"]
    for arr in ("bull_case", "bear_case", "key_risks"):
        assert isinstance(r[arr], list) and len(r[arr]) > 0
    assert isinstance(r["disclaimer"], str)


def _assert_extreme_superset(r):
    assert r["analysis_tier"] == "extreme"
    assert isinstance(r["factor_scores"], dict)
    assert isinstance(r["piotroski"], dict)
    assert isinstance(r["financial_trends"], dict)
    assert isinstance(r["extreme_thesis_md"], str)
    assert "scenarios" in r and "valuation_bands" in r


def test_cached_fixture_satisfies_ios_contract():
    """The stored extreme payload decodes against the iOS contract as-is (cache hit)."""
    r = _load()
    _assert_ios_contract(r)
    _assert_extreme_superset(r)


def test_normalize_response_preserves_contract():
    """_normalize_response(scan_type='extreme') guarantees the contract + superset."""
    orch = pytest.importorskip(
        "services.orchestrator",
        reason="orchestrator needs the full tradingagents stack (server-only)",
    )
    r = orch._normalize_response(_load(), scan_type="extreme")
    _assert_ios_contract(r)
    _assert_extreme_superset(r)
    # Idempotent: re-normalizing a normalized result is stable.
    again = orch._normalize_response(dict(r), scan_type="extreme")
    assert again["analysis_tier"] == "extreme"
    assert again["signal"] == r["signal"]
