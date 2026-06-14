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
        assert targets["upper_3m"] > 1000.0
        assert targets["lower_3m"] < 1000.0
        assert targets["upper_3m"] > targets["lower_3m"]

    def test_calibrated_confidence_bounds(self):
        from services.quant_engine import QuantitativeEngine
        engine = QuantitativeEngine("TEST")
        cc = engine._compute_calibrated_confidence(
            "Transition / Macro-Driven",
            {"Fundamental Health (F-Score)": 0.2},
            {"high_pledge_danger": False, "distressed_fundamentals": False}
        )
        assert 0.0 <= cc <= 1.0

    def test_tail_risk_depresses_confidence(self):
        from services.quant_engine import QuantitativeEngine
        engine = QuantitativeEngine("TEST")
        cc_normal = engine._compute_calibrated_confidence(
            "Transition / Macro-Driven", {}, {}
        )
        cc_risky = engine._compute_calibrated_confidence(
            "Transition / Macro-Driven", {},
            {"high_pledge_danger": True, "distressed_fundamentals": False}
        )
        assert cc_risky < cc_normal

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
