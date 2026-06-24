"""Unit tests for ML signal service and schema."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import httpx

from services.ml_signal_service import get_ml_signal, _direction_label
from schemas.ml_signal import MLSignalResponse, FeatureDriver, MLReliability


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def successful_ml_response():
    """Mock ML engine response for a successful prediction."""
    return {
        "direction": 1,
        "confidence": 0.63,
        "model_version": "lightgbm_alpha158_20260624",
        "ml_engine_mode": "trained_lightgbm_baseline",
        "lightgbm_loaded": True,
    }


def _make_mock_response(json_data, status_code=200):
    """Build a mock httpx.Response with the given JSON payload."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status.return_value = None
    return mock_resp


# ---------------------------------------------------------------------------
# 1. Success path
# ---------------------------------------------------------------------------

class TestMLSignalSuccess:
    """Verify the happy path: ML engine returns a valid prediction."""

    @patch("services.ml_signal_service._fetch_reliability", return_value=None)
    @patch("services.ml_signal_service.httpx.Client")
    def test_ml_signal_success(self, mock_client_cls, _mock_rel, successful_ml_response):
        """Successful ML engine response maps to ready MLSignalResponse."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = _make_mock_response(successful_ml_response)
        mock_client_cls.return_value = mock_client

        result = get_ml_signal("RELIANCE")

        assert isinstance(result, MLSignalResponse)
        assert result.status == "ready"
        assert result.direction == 1
        assert result.direction_label == "BULLISH"
        assert result.confidence == 0.63
        assert result.confidence_pct == 63
        assert result.model_version == "lightgbm_alpha158_20260624"
        assert result.ml_engine_mode == "trained_lightgbm_baseline"
        assert result.lightgbm_loaded is True
        assert result.symbol == "RELIANCE"
        assert result.warning is None


# ---------------------------------------------------------------------------
# 2. Timeout handling
# ---------------------------------------------------------------------------

class TestMLSignalTimeout:
    """ML engine timeout produces graceful unavailable response."""

    @patch("services.ml_signal_service._fetch_reliability", return_value=None)
    @patch("services.ml_signal_service.httpx.Client")
    def test_ml_signal_timeout(self, mock_client_cls, _mock_rel):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.TimeoutException("timed out")
        mock_client_cls.return_value = mock_client

        result = get_ml_signal("TCS")

        assert result.status == "unavailable"
        assert result.direction == 0
        assert result.direction_label == "NEUTRAL"
        assert result.confidence is None
        assert result.confidence_pct is None
        assert result.model_version is None
        assert result.reliability is None


# ---------------------------------------------------------------------------
# 3. Connection error handling
# ---------------------------------------------------------------------------

class TestMLSignalConnectionError:
    """ML engine connection refusal returns unavailable with warning."""

    @patch("services.ml_signal_service._fetch_reliability", return_value=None)
    @patch("services.ml_signal_service.httpx.Client")
    def test_ml_signal_connection_error(self, mock_client_cls, _mock_rel):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.ConnectError("connection refused")
        mock_client_cls.return_value = mock_client

        result = get_ml_signal("INFY")

        assert result.status == "unavailable"
        assert result.warning is not None
        assert "not running" in result.warning.lower() or "unavailable" in result.warning.lower()
        assert result.confidence is None
        assert result.confidence_pct is None
        assert result.reliability is None


# ---------------------------------------------------------------------------
# 4. Invalid response handling
# ---------------------------------------------------------------------------

class TestMLSignalInvalidResponse:
    """Non-JSON or malformed ML engine response handled gracefully."""

    @patch("services.ml_signal_service._fetch_reliability", return_value=None)
    @patch("services.ml_signal_service.httpx.Client")
    def test_ml_signal_invalid_response(self, mock_client_cls, _mock_rel):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.side_effect = ValueError("Invalid JSON")
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        result = get_ml_signal("HDFC")

        assert result.status == "unavailable"
        assert result.direction == 0
        assert result.direction_label == "NEUTRAL"


# ---------------------------------------------------------------------------
# 5. Direction label mappings
# ---------------------------------------------------------------------------

class TestMLSignalDirectionLabels:
    """All direction integer values map to correct string labels."""

    @pytest.mark.parametrize("direction,expected_label", [
        (1, "BULLISH"),
        (-1, "BEARISH"),
        (0, "NEUTRAL"),
    ])
    def test_direction_label_mapping(self, direction, expected_label):
        assert _direction_label(direction) == expected_label

    def test_direction_label_unknown_defaults_neutral(self):
        """Unrecognised direction values fall back to NEUTRAL."""
        assert _direction_label(2) == "NEUTRAL"
        assert _direction_label(-5) == "NEUTRAL"

    @pytest.mark.parametrize("direction,expected_label", [
        (1, "BULLISH"),
        (-1, "BEARISH"),
        (0, "NEUTRAL"),
    ])
    @patch("services.ml_signal_service._fetch_reliability", return_value=None)
    @patch("services.ml_signal_service.httpx.Client")
    def test_ml_signal_direction_labels(self, mock_client_cls, _mock_rel, direction, expected_label):
        """End-to-end: direction integer in ML response produces correct label."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = _make_mock_response({
            "direction": direction,
            "confidence": 0.50,
            "ml_engine_mode": "test",
        })
        mock_client_cls.return_value = mock_client

        result = get_ml_signal("SBIN")
        assert result.direction == direction
        assert result.direction_label == expected_label


# ---------------------------------------------------------------------------
# 6. Confidence percentage calculation
# ---------------------------------------------------------------------------

class TestMLSignalConfidencePct:
    """confidence_pct = int(confidence * 100)."""

    @pytest.mark.parametrize("raw_confidence,expected_pct", [
        (0.63, 63),
        (0.0, 0),
        (1.0, 100),
        (0.999, 99),
        (0.501, 50),
    ])
    @patch("services.ml_signal_service._fetch_reliability", return_value=None)
    @patch("services.ml_signal_service.httpx.Client")
    def test_ml_signal_confidence_pct_calculation(
        self, mock_client_cls, _mock_rel, raw_confidence, expected_pct
    ):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = _make_mock_response({
            "direction": 1,
            "confidence": raw_confidence,
            "ml_engine_mode": "test",
        })
        mock_client_cls.return_value = mock_client

        result = get_ml_signal("WIPRO")
        assert result.confidence_pct == expected_pct

    @patch("services.ml_signal_service._fetch_reliability", return_value=None)
    @patch("services.ml_signal_service.httpx.Client")
    def test_ml_signal_null_confidence_yields_null_pct(self, mock_client_cls, _mock_rel):
        """When ML engine omits confidence, both confidence and confidence_pct are None."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = _make_mock_response({
            "direction": 0,
            "ml_engine_mode": "fallback",
        })
        mock_client_cls.return_value = mock_client

        result = get_ml_signal("LT")
        assert result.confidence is None
        assert result.confidence_pct is None


# ---------------------------------------------------------------------------
# 7. Pydantic schema validation
# ---------------------------------------------------------------------------

class TestMLSignalSchemaValidation:
    """MLSignalResponse Pydantic model validates and serialises correctly."""

    def test_valid_ready_response(self):
        resp = MLSignalResponse(
            symbol="RELIANCE",
            direction=1,
            direction_label="BULLISH",
            confidence=0.63,
            confidence_pct=63,
            model_version="lightgbm_alpha158_20260624",
            ml_engine_mode="trained_lightgbm_baseline",
            lightgbm_loaded=True,
            generated_at=datetime.now(timezone.utc).isoformat(),
            status="ready",
        )
        assert resp.symbol == "RELIANCE"
        assert resp.direction_label == "BULLISH"
        assert resp.feature_drivers == []
        assert resp.reliability is None
        assert resp.warning is None

    def test_valid_unavailable_response(self):
        resp = MLSignalResponse(
            symbol="TCS",
            direction=0,
            direction_label="NEUTRAL",
            confidence=None,
            confidence_pct=None,
            model_version=None,
            ml_engine_mode="unavailable",
            lightgbm_loaded=False,
            generated_at=datetime.now(timezone.utc).isoformat(),
            status="unavailable",
            warning="ML engine is not running",
        )
        assert resp.status == "unavailable"
        assert resp.confidence is None
        assert resp.confidence_pct is None
        assert resp.model_version is None
        assert resp.reliability is None

    def test_schema_with_feature_drivers(self):
        drivers = [
            FeatureDriver(feature="RSI_14", contribution=0.12, direction="positive"),
            FeatureDriver(feature="MACD", contribution=-0.08, direction="negative"),
        ]
        resp = MLSignalResponse(
            symbol="INFY",
            direction=-1,
            direction_label="BEARISH",
            confidence=0.71,
            confidence_pct=71,
            ml_engine_mode="trained_lightgbm_baseline",
            lightgbm_loaded=True,
            generated_at=datetime.now(timezone.utc).isoformat(),
            feature_drivers=drivers,
            status="ready",
        )
        assert len(resp.feature_drivers) == 2
        assert resp.feature_drivers[0].feature == "RSI_14"
        assert resp.feature_drivers[1].direction == "negative"

    def test_schema_with_reliability(self):
        rel = MLReliability(
            hit_rate_30d=0.62,
            brier_score_30d=0.24,
            calibration_error_30d=0.08,
        )
        resp = MLSignalResponse(
            symbol="SBIN",
            direction=1,
            direction_label="BULLISH",
            ml_engine_mode="trained_lightgbm_baseline",
            generated_at=datetime.now(timezone.utc).isoformat(),
            reliability=rel,
            status="ready",
        )
        assert resp.reliability is not None
        assert resp.reliability.hit_rate_30d == 0.62

    def test_schema_rejects_missing_required_fields(self):
        """MLSignalResponse must reject construction without required fields."""
        with pytest.raises(Exception):
            MLSignalResponse(
                symbol="BAD",
                # missing direction, direction_label, ml_engine_mode, generated_at, status
            )
