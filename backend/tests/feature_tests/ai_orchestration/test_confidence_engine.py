import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
import pandas as pd

from services.confidence_engine import (
    compute_signal_agreement, 
    apply_bear_asymmetry, 
    compute_final_confidence,
    compute_conformal_bounds,
    find_historical_analogues,
    _extract_feature_row,
)

def test_compute_signal_agreement():
    reports = {
        "governance": "The signal is CAUTIOUSLY BULLISH.",
        "market": "The signal is BEARISH.",
        "fundamentals": "The signal is NEUTRAL.",
        "news": "The signal is BULLISH."
    }
    res = compute_signal_agreement(reports)
    assert res["total_voters"] == 4
    # "CAUTIOUSLY BULLISH" -> "BULLISH", "BULLISH" -> "BULLISH" => 2/4 BULLISH
    assert res["vote_counts"]["BULLISH"] == 2
    assert res["agreement_ratio"] == 0.5  # 2 out of 4

def test_compute_signal_agreement_empty():
    res = compute_signal_agreement({})
    assert res["total_voters"] == 0
    assert res["agreement_ratio"] == 0.0

def test_apply_bear_asymmetry():
    output = "Bull confidence: 60%. Bear confidence: 40%."
    res = apply_bear_asymmetry(output)
    
    assert res["bull_confidence"] == 0.60
    assert res["bear_confidence"] == 0.40
    # net_direction = (0.6 * 1.0 - 0.4 * 1.5) / 2.5 = 0.0
    assert res["net_direction"] == 0.0
    assert res["signal_override"] == "NEUTRAL"

def test_compute_final_confidence():
    res = compute_final_confidence(
        raw_llm_confidence=80,
        governance_score=35, # < 40 triggers cap
        signal_agreement_ratio=0.75,
        regime_multiplier=1.0,
        delivery_modifier=0.0,
        microstructure_modifier=0.0,
        rrg_modifier=0.0,
        minskyan_penalty=0.0,
        monsoon_modifier=0.0,
        cisi_modifier=0.0,
        auditor_boost=0.0,
        bear_asymmetry_adjustment=0.0,
        signal="BULLISH"
    )
    assert res["governance_cap_applied"] is True
    # The cap value is 40
    assert res["final_confidence_pct"] <= 40

def test_compute_final_confidence_no_cap():
    res = compute_final_confidence(
        raw_llm_confidence=80,
        governance_score=85, # > 40
        signal_agreement_ratio=1.0,
        regime_multiplier=1.0,
        delivery_modifier=0.05,
        microstructure_modifier=0.05,
        rrg_modifier=0.0,
        minskyan_penalty=0.0,
        monsoon_modifier=0.0,
        cisi_modifier=0.0,
        auditor_boost=0.0,
        bear_asymmetry_adjustment=0.1,
        signal="BULLISH"
    )
    assert res["governance_cap_applied"] is False
    assert res["final_confidence_pct"] > 80  # Thanks to positive modifiers

def test_compute_conformal_bounds_no_data():
    res = compute_conformal_bounds("RELIANCE", 100.0, None)
    assert "short_term_3m" in res
    assert res["short_term_3m"]["mid"] == 100.0
    assert res["short_term_3m"]["lower"] is None
    assert res["short_term_3m"]["upper"] is None
    assert res["short_term_3m"]["method"] == "empirical_rolling_quantile"

def test_compute_conformal_bounds_insufficient_data():
    # Provide a dataframe with < 63 rows (e.g. 5 rows)
    df = pd.DataFrame({"Close": [100.0] * 5})
    res = compute_conformal_bounds("RELIANCE", 100.0, df)
    for horizon in ("short_term_3m", "medium_term_12m", "long_term_36m"):
        assert res[horizon]["lower"] is None
        assert res[horizon]["upper"] is None
        assert res[horizon]["method"] == "empirical_rolling_quantile"


def test_compute_conformal_bounds_sufficient_data_labelled_empirical():
    df = pd.DataFrame({"Close": [100.0 + (i % 7) for i in range(120)]})
    res = compute_conformal_bounds("RELIANCE", 100.0, df)
    short = res["short_term_3m"]
    assert short["method"] == "empirical_rolling_quantile"
    assert short["lower"] is not None and short["upper"] is not None
    assert short["lower"] <= short["upper"]
    assert res["long_term_36m"]["lower"] is None  # 120 rows < 756


# ── ML-22: KNN analogue containment ──────────────────────────────────────────

def test_extract_feature_row_rejects_default_only_rows():
    only_fundamentals = json.dumps({"fundamentals_snapshot": {"pe_ratio": 22.0, "promoter_pledged_pct": 1.0}})
    assert _extract_feature_row(only_fundamentals) is None


def test_extract_feature_row_distinguishes_rsi():
    base = {"price_vs_sma50_pct": 2.0, "hist_vol_21_annualized": 22.0, "momentum_score": 0.1}
    a = _extract_feature_row(json.dumps({**base, "rsi_14": 25.0}))
    b = _extract_feature_row(json.dumps({**base, "rsi_14": 75.0}))
    assert a is not None and b is not None
    assert float(np.linalg.norm(a - b)) > 0


def _fake_session_factory(rows):
    @contextmanager
    def _fake_get_session():
        session = MagicMock()
        session.query.return_value.filter.return_value.order_by.return_value \
            .limit.return_value.all.return_value = rows
        yield session
    return _fake_get_session


def _analogue_rows(n_labelled, n_total=12):
    rows = []
    for i in range(n_total):
        full_json = json.dumps({
            "rsi_14": 30.0 + i,
            "price_vs_sma50_pct": 1.0 + i,
            "hist_vol_21_annualized": 20.0 + i,
            "momentum_score": 0.1 * i,
        })
        labelled = i < n_labelled
        # Even rows: correct bearish calls (stock fell, so the delta is negative).
        rows.append(SimpleNamespace(
            full_json=full_json,
            was_correct=(i % 2 == 0) if labelled else None,
            outcome_delta_pct=(-4.0 if i % 2 == 0 else 3.0) if labelled else None,
        ))
    return rows


def test_analogue_summary_wording_and_min_outcomes(monkeypatch):
    features = {"rsi_14": 35.0, "price_vs_sma50_pct": 3.0,
                "hist_vol_21_annualized": 24.0, "momentum_score": 0.3}

    # Exactly 10 labelled rows, so all are the top-10 and 5 (even rows) are correct.
    # find_historical_analogues resolves get_session from its module globals.
    module_globals = find_historical_analogues.__globals__
    monkeypatch.setitem(module_globals, "get_session", _fake_session_factory(_analogue_rows(10, n_total=10)))
    res = find_historical_analogues("TCS", features)
    assert res["k_found"] == 10
    assert "directionally correct" in res["analogue_summary"]
    assert "positive returns" not in res["analogue_summary"]
    assert res["historical_win_rate_pct"] == 50.0
    assert res["avg_return_on_wins_pct"] is None

    monkeypatch.setitem(module_globals, "get_session", _fake_session_factory(_analogue_rows(5)))
    res = find_historical_analogues("TCS", features)
    assert res["historical_win_rate_pct"] is None
    assert "insufficient outcome history" in res["analogue_summary"]


def test_orchestrator_has_no_dead_bootstrap_block():
    import inspect
    import os

    services_dir = os.path.dirname(inspect.getfile(compute_conformal_bounds))
    src = open(os.path.join(services_dir, "orchestrator.py")).read()
    assert "analogue_returns" not in src
    assert "MonteCarloBootstrapEngine" not in src
