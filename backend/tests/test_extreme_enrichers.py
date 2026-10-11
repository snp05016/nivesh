"""Task 4 — deterministic extreme bundles: correct keys, real shapes, graceful degradation."""
import services.extreme_enrichers as ex


def _boom(*a, **k):
    raise RuntimeError("down")


def test_all_keys_present_and_graceful(monkeypatch):
    # every underlying source blows up → bundles must not raise, must return safe defaults
    import services.nse_data_provider as ndp
    monkeypatch.setattr(ndp, "get_fundamentals", _boom)
    monkeypatch.setattr(ex, "_compute_piotroski", lambda *a, **k: None)
    monkeypatch.setattr(ex, "_financial_trends", lambda *a, **k: None)
    monkeypatch.setattr(ex, "_ownership_trends", lambda *a, **k: None)
    # nse_data_provider is the real module in tests (TEST-12); no peer source is
    # wired yet, so stub the peer bundle to its production value.
    monkeypatch.setattr(ex, "_peer_comparison", lambda *a, **k: [])
    out = ex.build_extreme_bundles("ZZZZ", "NSE")
    assert set(out) == {"factor_scores", "piotroski", "financial_trends",
                        "ownership_trends", "peer_comparison"}
    assert out["peer_comparison"] == []          # no peer source wired yet
    assert out["piotroski"] is None


def test_factor_scores_from_fundamentals(monkeypatch):
    import services.nse_data_provider as ndp
    monkeypatch.setattr(ndp, "get_fundamentals",
                        lambda t, e="NSE": {"pe_ratio": 20, "pb_ratio": 4,
                                            "roe": 0.25, "debt_to_equity": 40})
    # no price history → momentum/low_vol None, but value/quality computed
    monkeypatch.setattr(ex, "_momentum_score", lambda *a, **k: None)
    monkeypatch.setattr(ex, "_low_volatility_score", lambda *a, **k: None)
    fs = ex._compute_factor_scores("RELIANCE", "NSE")
    assert fs is not None
    assert 0 <= fs["value"] <= 100
    assert 0 <= fs["quality"] <= 100
    assert fs["momentum"] is None


def test_factor_scores_none_when_no_data(monkeypatch):
    import services.nse_data_provider as ndp
    monkeypatch.setattr(ndp, "get_fundamentals", lambda *a, **k: {})
    monkeypatch.setattr(ex, "_momentum_score", lambda *a, **k: None)
    monkeypatch.setattr(ex, "_low_volatility_score", lambda *a, **k: None)
    assert ex._compute_factor_scores("ZZZZ", "NSE") is None


def test_clamp_bounds():
    assert ex._clamp(-50) == 0
    assert ex._clamp(150) == 100
    assert ex._clamp(63.4) == 63
