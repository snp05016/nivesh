"""Unit tests for QuantitativeEngine mathematical correctness."""
import pytest
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

class TestQuantEngineMath:
    """Test core mathematical functions without network calls."""

    def test_regime_detection_low_vol(self):
        from services.quant_engine import QuantitativeEngine
        engine = QuantitativeEngine("TEST")
        regime = engine._detect_market_regime({"annualized_volatility_30d": 0.10})
        assert regime == "Low Volatility / Accumulation"

    def test_regime_detection_transition(self):
        from services.quant_engine import QuantitativeEngine
        engine = QuantitativeEngine("TEST")
        regime = engine._detect_market_regime({"annualized_volatility_30d": 0.18})
        assert regime == "Transition / Macro-Driven"

    def test_regime_detection_crisis(self):
        from services.quant_engine import QuantitativeEngine
        engine = QuantitativeEngine("TEST")
        regime = engine._detect_market_regime({"annualized_volatility_30d": 0.30})
        assert regime == "High Volatility / Crisis"

    def test_conformal_targets(self):
        from services.quant_engine import QuantitativeEngine
        engine = QuantitativeEngine("TEST")
        targets = engine._compute_conformal_targets({
            "current_price": 1000.0,
            "daily_volatility": 0.02
        })
        upper, lower = targets["upper_3m"], targets["lower_3m"]
        assert upper is not None and lower is not None
        assert upper > 1000.0
        assert lower < 1000.0
        assert upper > lower

    def test_vol_range_symmetric(self):
        """FAKE-17: the 3M range has no hardcoded drift, so it is centred on price."""
        from services.quant_engine import QuantitativeEngine
        targets = QuantitativeEngine._compute_conformal_targets({
            "current_price": 100.0,
            "daily_volatility": 0.01,
        })
        upper, lower = targets["upper_3m"], targets["lower_3m"]
        assert upper is not None and lower is not None
        assert upper - 100.0 == pytest.approx(100.0 - lower, abs=1e-6)

    def test_vol_range_none_without_price(self):
        """ML-20: no current price means no range, not a 0.0 range."""
        from services.quant_engine import QuantitativeEngine
        targets = QuantitativeEngine._compute_conformal_targets(
            QuantitativeEngine._fallback_market_data())
        assert targets == {"upper_3m": None, "lower_3m": None}

    def test_calibrated_confidence_bounds(self):
        from services.quant_engine import QuantitativeEngine
        engine = QuantitativeEngine("TEST")
        cc, breakdown = engine._compute_calibrated_confidence(
            "Transition / Macro-Driven",
            {"Fundamental Health (F-Score)": 0.2},
            {"high_pledge_danger": False, "distressed_fundamentals": False}
        )
        assert 0.0 <= cc <= 1.0
        assert breakdown == {
            "base_probability": 0.5,
            "net_shap_adjustment": 0.2,
            "regime_multiplier": 0.85,
            "tail_risk_deduction": 0.0,
            "final_calibrated_confidence": cc,
        }

    def test_tail_risk_depresses_confidence(self):
        from services.quant_engine import QuantitativeEngine
        engine = QuantitativeEngine("TEST")
        cc_normal, breakdown_normal = engine._compute_calibrated_confidence(
            "Transition / Macro-Driven", {}, {}
        )
        cc_risky, breakdown_risky = engine._compute_calibrated_confidence(
            "Transition / Macro-Driven", {},
            {"high_pledge_danger": True, "distressed_fundamentals": False}
        )
        assert cc_risky < cc_normal
        assert breakdown_normal["tail_risk_deduction"] == 0.0
        assert breakdown_risky["tail_risk_deduction"] == 0.3

    def test_feature_importance_filters_negligible(self):
        from services.quant_engine import QuantitativeEngine
        engine = QuantitativeEngine("TEST")
        drivers, _ = engine._compute_feature_importance(
            {"piotroski_score": 5, "promoter_pledge_pct": 0.0},
            {"rsi_14": 50.0}
        )
        # F-Score = (5-5)/4*0.40 = 0.0, RSI=50 gives no signal, pledge=0 gives no signal
        # All should be filtered out (abs < 0.05)
        assert len(drivers) == 0 or all(abs(v) > 0.05 for v in drivers.values())

    def test_rsi_calculation(self):
        from services.quant_engine import QuantitativeEngine
        import numpy as np
        engine = QuantitativeEngine("TEST")
        # All gains
        prices = np.array([100.0 + i for i in range(20)])
        rsi = engine._compute_rsi(prices, 14)
        assert rsi == 100.0
        # All losses
        prices = np.array([100.0 - i for i in range(20)])
        rsi = engine._compute_rsi(prices, 14)
        assert rsi == 0.0


class TestQuantEngineUnknownInputs:
    """FAKE-16: missing inputs are reported as unavailable, never imputed."""

    def test_fundamentals_failure_marked_unavailable(self, monkeypatch):
        from services.quant_engine import QuantitativeEngine

        async def _boom(self):
            raise RuntimeError("NSE fundamentals timeout")

        async def _market(self):
            return {"current_price": 1000.0, "daily_volatility": 0.01,
                    "annualized_volatility_30d": 0.16, "rsi_14": 55.0, "fallback": False}

        monkeypatch.setattr(QuantitativeEngine, "_fetch_fundamentals", _boom)
        monkeypatch.setattr(QuantitativeEngine, "_fetch_market_volatility", _market)

        payload = asyncio.run(QuantitativeEngine("TCS").run_full_pipeline())
        assert payload["data_quality"] == {"fundamentals": "unavailable", "market": "ok"}
        assert "Fundamental Health (F-Score)" not in payload["quantitative_drivers"]
        assert "Promoter Pledge Risk" not in payload["quantitative_drivers"]
        assert "high_pledge_danger" not in payload["tail_risk_flags"]
        assert "distressed_fundamentals" not in payload["tail_risk_flags"]

    def test_market_fallback_has_no_rsi(self):
        from services.quant_engine import QuantitativeEngine
        fb = QuantitativeEngine._fallback_market_data()
        assert fb["rsi_14"] is None and fb["fallback"] is True
        drivers, tails = QuantitativeEngine._compute_feature_importance(
            {"piotroski_score": None, "promoter_pledge_pct": None}, fb
        )
        assert drivers == {} and tails == {}

    def test_known_inputs_still_flag_risk(self):
        from services.quant_engine import QuantitativeEngine
        drivers, tails = QuantitativeEngine._compute_feature_importance(
            {"piotroski_score": 2, "promoter_pledge_pct": 45.0}, {"rsi_14": 25.0}
        )
        assert tails == {"high_pledge_danger": True, "distressed_fundamentals": True}
        assert drivers["Technical Reversion (Oversold)"] == 0.25

    def test_no_zero_input_minskyan(self):
        src = open(os.path.join(os.path.dirname(__file__), "..", "services", "orchestrator.py")).read()
        assert "compute_minskyan_risk(dii_ytd=0, fii_ytd=0)" not in src


_OK_MARKET = {"current_price": 1000.0, "daily_volatility": 0.01,
              "annualized_volatility_30d": 0.16, "rsi_14": 25.0, "fallback": False}
_OK_FUNDAMENTALS = {"piotroski_score": 8, "promoter_pledge_pct": 10.0,
                    "pe_ratio": 22.0, "roe": 18.0, "fallback": False}


def _patch_fetchers(monkeypatch, market, fundamentals):
    from services.quant_engine import QuantitativeEngine

    async def _market(self):
        return market

    async def _fund(self):
        return fundamentals

    monkeypatch.setattr(QuantitativeEngine, "_fetch_market_volatility", _market)
    monkeypatch.setattr(QuantitativeEngine, "_fetch_fundamentals", _fund)
    return QuantitativeEngine


class TestQuantEngineHonestOutput:
    """ML-20: heuristic outputs are labelled as such and never built on fallbacks."""

    def test_degraded_market_data_nulls_confidence(self, monkeypatch):
        from services.quant_engine import QuantitativeEngine
        engine_cls = _patch_fetchers(
            monkeypatch, QuantitativeEngine._fallback_market_data(), dict(_OK_FUNDAMENTALS))
        payload = asyncio.run(engine_cls("TCS").run_full_pipeline())
        assert payload["method"] == "rule_based_heuristic"
        assert payload["data_quality"]["market"] == "unavailable"
        assert payload["calibrated_confidence"] is None
        assert payload["confidence_math_breakdown"] == {}
        assert payload["market_regime"] == "Data Unavailable"
        assert payload["conformal_target_upper_3m"] is None
        assert payload["conformal_target_lower_3m"] is None
        assert not any(k.startswith("Technical") for k in payload["quantitative_drivers"])

    def test_degraded_fundamentals_drops_fscore_driver(self, monkeypatch):
        engine_cls = _patch_fetchers(
            monkeypatch, dict(_OK_MARKET),
            {"piotroski_score": None, "promoter_pledge_pct": None, "fallback": True})
        payload = asyncio.run(engine_cls("TCS").run_full_pipeline())
        assert payload["data_quality"] == {"fundamentals": "unavailable", "market": "ok"}
        assert payload["calibrated_confidence"] is None
        assert "Fundamental Health (F-Score)" not in payload["quantitative_drivers"]
        assert "Promoter Pledge Risk" not in payload["quantitative_drivers"]
        # Market-derived pieces are still real and still reported.
        assert payload["quantitative_drivers"]["Technical Reversion (Oversold)"] == 0.25
        assert payload["conformal_target_upper_3m"] > 1000.0

    def test_ok_inputs_keep_confidence(self, monkeypatch):
        engine_cls = _patch_fetchers(monkeypatch, dict(_OK_MARKET), dict(_OK_FUNDAMENTALS))
        payload = asyncio.run(engine_cls("TCS").run_full_pipeline())
        assert payload["data_quality"] == {"fundamentals": "ok", "market": "ok"}
        assert isinstance(payload["calibrated_confidence"], float)
        assert 0.05 <= payload["calibrated_confidence"] <= 0.95
        assert payload["market_regime"] == "Transition / Macro-Driven"
        # iOS decodes the breakdown as [String: Double]; every value must be numeric.
        assert all(isinstance(v, (int, float)) for v in payload["confidence_math_breakdown"].values())

    def test_no_dead_macro_fetch(self):
        from services.quant_engine import QuantitativeEngine
        assert not hasattr(QuantitativeEngine, "_fetch_macro_indicators")

    def test_prompt_header_not_authoritative(self):
        here = os.path.dirname(__file__)
        orch = open(os.path.join(here, "..", "services", "orchestrator.py")).read()
        prompts = open(os.path.join(here, "..", "prompts.py")).read()
        assert "QUANTITATIVE ENGINE OUTPUT (AUTHORITATIVE)" not in orch
        assert "CALIBRATION ENGINE OUTPUT (AUTHORITATIVE)" not in orch
        assert "exact SHAP values" not in prompts
        assert "Quantitative ML Engine" not in prompts

    def test_placeholder_macro_endpoints_removed(self):
        import services.macro_modifiers as mm
        for name in ("get_monsoon_modifier", "_fetch_imd_status", "fetch_fii_dii_ytd"):
            assert not hasattr(mm, name)
        assert callable(mm.compute_minskyan_risk)
