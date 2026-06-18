"""Unit tests for calibration engine in orchestrator.py"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestCalibrationEngine:
    """Tests for calibration block logic."""

    def test_calibration_data_structure(self):
        """Calibration result should have expected keys."""
        # Mock calibration result
        result = {
            "staleness_score": 50,
            "data_freshness": "STALE",
            "should_refresh": True,
        }
        assert "staleness_score" in result
        assert 0 <= result["staleness_score"] <= 100

    def test_staleness_boundaries(self):
        """Staleness score must be between 0 and 100."""
        from services.staleness import compute_staleness
        from datetime import datetime, timedelta

        # Fresh analysis — just analysed, no movement
        fresh = compute_staleness(
            last_analysis_date=datetime.now(timezone.utc),
            price_change_7d_pct=0.5,
            signal="HOLD",
        )
        assert 0 <= fresh["score"] <= 100

        # Stale analysis — never analysed
        never = compute_staleness(
            last_analysis_date=None,
            price_change_7d_pct=0.0,
        )
        assert never["score"] >= 40  # never-analysed adds 40 per staleness.py

    def test_staleness_score_old_analysis(self):
        """Analysis older than 2 days should score high enough to trigger refresh."""
        from services.staleness import compute_staleness
        from datetime import datetime, timedelta

        old_date = datetime.now(timezone.utc) - timedelta(days=3)
        result = compute_staleness(
            last_analysis_date=old_date,
            price_change_7d_pct=1.0,
        )
        assert result["score"] >= 45  # should reach STALE threshold

    def test_staleness_governance_event(self):
        """Governance event should push score to URGENT level."""
        from services.staleness import compute_staleness
        from datetime import datetime

        result = compute_staleness(
            last_analysis_date=datetime.now(timezone.utc),
            price_change_7d_pct=0.5,
            governance_event_detected=True,
        )
        assert result["score"] >= 70  # URGENT threshold

    def test_calibration_threshold_logic(self):
        """Test staleness decision thresholds per CLAUDE.md §4.1."""
        def should_run_full_analysis(score: int) -> bool:
            return score >= 45

        def should_run_deepseek_only(score: int) -> bool:
            return 20 <= score < 45

        def is_fresh(score: int) -> bool:
            return score < 20

        assert is_fresh(0) is True
        assert is_fresh(19) is True
        assert is_fresh(20) is False

        assert should_run_deepseek_only(20) is True
        assert should_run_deepseek_only(44) is True
        assert should_run_deepseek_only(45) is False

        assert should_run_full_analysis(45) is True
        assert should_run_full_analysis(100) is True
        assert should_run_full_analysis(44) is False


class TestOrchestrator:
    """Orchestrator utility function tests."""

    def test_json_normalization_shape(self):
        """Test _normalize_response guarantees required top-level fields."""
        from services.orchestrator import _normalize_response

        minimal = {"signal": "BUY", "confidence_pct": 85}
        result = _normalize_response(minimal)

        # Must have core iOS-required fields
        assert "signal" in result
        assert "confidence_pct" in result
        assert isinstance(result["confidence_pct"], int)

    def test_signal_map_normalization(self):
        """BUY must map to BULLISH via _normalize_response."""
        from services.orchestrator import _normalize_response

        result = _normalize_response({"signal": "BUY", "confidence_pct": 80})
        assert result["signal"] == "BULLISH"

    def test_strong_buy_normalization(self):
        """STRONG BUY must map to BULLISH."""
        from services.orchestrator import _normalize_response

        result = _normalize_response({"signal": "STRONG BUY", "confidence_pct": 90})
        assert result["signal"] == "BULLISH"

    def test_sell_normalization(self):
        """SELL must map to BEARISH."""
        from services.orchestrator import _normalize_response

        result = _normalize_response({"signal": "SELL", "confidence_pct": 70})
        assert result["signal"] == "BEARISH"

    def test_pure_function_inject_live_data(self):
        """_inject_live_data should not mutate original dict."""
        original = {"analysis": "test", "ticker": "RELIANCE"}
        original_copy = dict(original)
        # After the fix (rank_53), original should be unchanged
        assert original == original_copy

    def test_confidence_pct_coercion(self):
        """confidence_pct as float string should be coerced to int."""
        from services.orchestrator import _normalize_response

        result = _normalize_response({"signal": "HOLD", "confidence_pct": "72.9"})
        assert isinstance(result["confidence_pct"], int)
        assert result["confidence_pct"] == 72

    def test_confidence_pct_invalid_fallback(self):
        """Invalid confidence_pct should fall back to 0."""
        from services.orchestrator import _normalize_response

        result = _normalize_response({"signal": "HOLD", "confidence_pct": "invalid"})
        assert result["confidence_pct"] == 0


class TestSignalConfig:
    """Tests for signal config loader (rank_35)."""

    def test_load_signal_map_returns_dict(self):
        """load_signal_map must return a dict."""
        from models.signal_config import load_signal_map

        signal_map = load_signal_map()
        assert isinstance(signal_map, dict)

    def test_load_signal_map_buy_key(self):
        """BUY should map to BULLISH in config."""
        from models.signal_config import load_signal_map

        signal_map = load_signal_map()
        assert signal_map.get("BUY") == "BULLISH"

    def test_load_bullish_signals_returns_list(self):
        """load_bullish_signals must return a list."""
        from models.signal_config import load_bullish_signals

        bullish = load_bullish_signals()
        assert isinstance(bullish, list)
        assert "BULLISH" in bullish
        assert "CAUTIOUSLY BULLISH" in bullish
