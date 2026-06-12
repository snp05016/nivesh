"""Task 5 — extreme output is an additive superset; standard output is untouched."""


def test_extreme_normalizer_guarantees_blocks():
    from services.orchestrator import _normalize_response
    out = _normalize_response({"signal": "BUY", "confidence_pct": 70}, "extreme")
    for k in ("scenarios", "valuation_bands", "extended_thesis",
              "niche_insights", "governance_flags", "analysis_tier"):
        assert k in out, f"missing extreme field: {k}"
    assert out["analysis_tier"] == "extreme"
    assert isinstance(out["niche_insights"], list)
    assert isinstance(out["governance_flags"], list)


def test_extreme_normalizer_preserves_llm_values():
    from services.orchestrator import _normalize_response
    given = {"signal": "BUY", "niche_insights": ["hidden capex cycle"],
             "scenarios": {"bull": {"price_12m": 100}}}
    out = _normalize_response(given, "extreme")
    assert out["niche_insights"] == ["hidden capex cycle"]   # setdefault must not clobber
    assert out["scenarios"]["bull"]["price_12m"] == 100


def test_standard_normalizer_unchanged():
    from services.orchestrator import _normalize_response
    out = _normalize_response({"signal": "HOLD"}, "standard")
    assert "scenarios" not in out
    assert "analysis_tier" not in out


def test_standard_default_scan_type():
    """Existing positional callers (one arg) still work and stay standard."""
    from services.orchestrator import _normalize_response
    out = _normalize_response({"signal": "HOLD"})
    assert "scenarios" not in out


def test_addendum_present_and_additive():
    # conftest mocks the `prompts` module, so read the real source from disk.
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "prompts.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert "EXTREME_ADDENDUM" in src
    addendum = src.split("EXTREME_ADDENDUM", 1)[1]
    assert "EXTREME MODE" in addendum
    assert "scenarios" in addendum and "governance_flags" in addendum
    # the base prompt section must NOT contain the extreme directive
    base = src.split("EXTREME_ADDENDUM", 1)[0]
    assert "EXTREME MODE" not in base
