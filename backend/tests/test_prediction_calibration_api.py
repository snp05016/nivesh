"""
API-level tests for Prediction Calibration endpoints.

Endpoints under test:
  GET /api/v1/predictions/calibration
  GET /api/v1/predictions/pillar-attribution
  GET /api/v1/predictions/model-versions
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_USER_ID = 1


from helpers import require_auth
from core.security import require_admin

@pytest.fixture()
def authed_client():
    """TestClient with require_auth bypassed to return a fixed user_id."""
    app.dependency_overrides[require_auth] = lambda: MOCK_USER_ID
    app.dependency_overrides[require_admin] = lambda: MOCK_USER_ID
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def unauthed_client():
    """TestClient without any auth bypass (real require_auth runs)."""
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Calibration stub data
# ---------------------------------------------------------------------------

EMPTY_CALIBRATION = {
    "confidence_bucket_accuracy": [],
    "brier_score_by_bucket": [],
    "overconfidence_by_bucket": [],
    "calibration_error": None,
    "expected_calibration_error": None,
    "max_calibration_error": None,
    "hit_rate_by_horizon": {},
    "calibration_by_scan_type": [],
    "calibration_by_regime": [],
    "calibration_by_sector": [],
    "calibration_by_ml_engine_mode": [],
    "calibration_by_recommendation": [],
}

SAMPLE_CALIBRATION = {
    "confidence_bucket_accuracy": [
        {"bucket_label": "70-80%", "count": 12, "accuracy": 0.75,
         "avg_brier_score": 0.18, "avg_confidence": 0.74, "overconfidence": -0.01},
    ],
    "brier_score_by_bucket": [
        {"bucket_label": "70-80%", "count": 12, "accuracy": 0.75,
         "avg_brier_score": 0.18, "avg_confidence": 0.74, "overconfidence": -0.01},
    ],
    "overconfidence_by_bucket": [
        {"bucket_label": "70-80%", "count": 12, "accuracy": 0.75,
         "avg_brier_score": 0.18, "avg_confidence": 0.74, "overconfidence": -0.01},
    ],
    "calibration_error": 0.05,
    "expected_calibration_error": 0.04,
    "max_calibration_error": 0.12,
    "hit_rate_by_horizon": {
        "7d": {"matured_count": 5, "hit_rate": 0.6},
        "30d": {"matured_count": 10, "hit_rate": 0.7},
        "90d": {"matured_count": 3, "hit_rate": 0.67},
    },
    "calibration_by_scan_type": [
        {"group_key": "standard", "count": 15, "accuracy": 0.73,
         "avg_brier_score": 0.19, "avg_confidence": 0.72, "calibration_error": 0.01},
    ],
    "calibration_by_regime": [],
    "calibration_by_sector": [],
    "calibration_by_ml_engine_mode": [],
    "calibration_by_recommendation": [],
}


# ---------------------------------------------------------------------------
# Pillar attribution stub data
# ---------------------------------------------------------------------------

EMPTY_PILLAR_ATTRIBUTION = {
    "pillars": {},
    "total_predictions": 0,
}

SAMPLE_PILLAR_ATTRIBUTION = {
    "pillars": {
        "llm_confidence": {
            "correlation_with_hit_30d": 0.35,
            "bucketed_accuracy": [
                {"range": "70-80%", "count": 8, "hit_rate": 0.75,
                 "avg_brier_score_30d": 0.17, "avg_confidence": 0.74, "overconfidence": -0.01},
            ],
            "avg_brier_score_30d": 0.19,
            "predictive_lift": 0.02,
            "missing_rate": 0.0,
            "usefulness_rank": 1,
        },
        "quant_confidence": {
            "correlation_with_hit_30d": 0.28,
            "bucketed_accuracy": [],
            "avg_brier_score_30d": 0.22,
            "predictive_lift": -0.01,
            "missing_rate": 0.1,
            "usefulness_rank": 2,
        },
        "venn_abers_confidence": {
            "correlation_with_hit_30d": 0.20,
            "bucketed_accuracy": [],
            "avg_brier_score_30d": 0.25,
            "predictive_lift": -0.03,
            "missing_rate": 0.15,
            "usefulness_rank": 3,
        },
        "signal_agreement": {
            "correlation_with_hit_30d": 0.15,
            "bucketed_accuracy": [],
            "avg_brier_score_30d": 0.30,
            "predictive_lift": -0.05,
            "missing_rate": 0.05,
            "usefulness_rank": 4,
        },
        "ml_confidence": {
            "correlation_with_hit_30d": 0.10,
            "bucketed_accuracy": [],
            "avg_brier_score_30d": 0.35,
            "predictive_lift": -0.08,
            "missing_rate": 0.20,
            "usefulness_rank": 5,
        },
    },
    "total_predictions": 50,
}

EXPECTED_PILLAR_NAMES = {
    "llm_confidence",
    "quant_confidence",
    "venn_abers_confidence",
    "signal_agreement",
    "ml_confidence",
}


# ---------------------------------------------------------------------------
# Model versions stub data
# ---------------------------------------------------------------------------

EMPTY_MODEL_VERSIONS = {
    "versions": [],
    "total_predictions": 0,
}

SAMPLE_MODEL_VERSIONS = {
    "versions": [
        {
            "model_version": "v2.1",
            "ml_engine_mode": "ensemble",
            "total_predictions": 30,
            "hit_rate_7d": 0.60,
            "hit_rate_30d": 0.70,
            "hit_rate_90d": 0.65,
            "average_return_30d": 2.5,
            "brier_score_30d": 0.18,
            "calibration_error_30d": 0.03,
            "confidence_avg": 0.72,
            "confidence_realized_accuracy_gap": -0.02,
        },
    ],
    "total_predictions": 30,
}

MODEL_VERSION_REQUIRED_FIELDS = {
    "model_version",
    "total_predictions",
    "hit_rate_7d",
    "hit_rate_30d",
    "hit_rate_90d",
    "average_return_30d",
    "brier_score_30d",
    "calibration_error_30d",
    "confidence_avg",
    "confidence_realized_accuracy_gap",
}


# ===========================================================================
# 1. Calibration endpoint — basic 200
# ===========================================================================

class TestCalibrationEndpoint:

    @patch(
        "routers.predictions.get_calibration_metrics",
        return_value=SAMPLE_CALIBRATION,
    )
    def test_calibration_endpoint_returns_200(self, _mock, authed_client):
        resp = authed_client.get("/api/v1/predictions/calibration")
        assert resp.status_code == 200

    # -----------------------------------------------------------------------
    # 2. Calibration response schema
    # -----------------------------------------------------------------------

    @patch(
        "routers.predictions.get_calibration_metrics",
        return_value=SAMPLE_CALIBRATION,
    )
    def test_calibration_response_schema(self, _mock, authed_client):
        resp = authed_client.get("/api/v1/predictions/calibration")
        assert resp.status_code == 200
        data = resp.json()

        expected_keys = {
            "confidence_bucket_accuracy",
            "brier_score_by_bucket",
            "overconfidence_by_bucket",
            "calibration_error",
            "expected_calibration_error",
            "max_calibration_error",
            "hit_rate_by_horizon",
            "calibration_by_scan_type",
            "calibration_by_regime",
            "calibration_by_sector",
            "calibration_by_ml_engine_mode",
            "calibration_by_recommendation",
        }
        assert expected_keys.issubset(data.keys()), (
            f"Missing keys: {expected_keys - data.keys()}"
        )

        # List fields must be lists
        for k in [
            "confidence_bucket_accuracy",
            "brier_score_by_bucket",
            "overconfidence_by_bucket",
            "hit_rate_by_horizon",
            "calibration_by_scan_type",
            "calibration_by_regime",
            "calibration_by_sector",
            "calibration_by_ml_engine_mode",
            "calibration_by_recommendation",
        ]:
            assert isinstance(data[k], list), f"{k} should be a list"

        # Scalar calibration fields must be float or None
        for k in ["calibration_error", "expected_calibration_error", "max_calibration_error"]:
            assert data[k] is None or isinstance(data[k], (int, float)), (
                f"{k} should be float or None, got {type(data[k])}"
            )


# ===========================================================================
# 3. Pillar attribution endpoint — basic 200
# ===========================================================================

class TestPillarAttributionEndpoint:

    @patch(
        "routers.predictions.get_pillar_attribution",
        return_value=SAMPLE_PILLAR_ATTRIBUTION,
    )
    def test_pillar_attribution_endpoint_returns_200(self, _mock, authed_client):
        resp = authed_client.get("/api/v1/predictions/pillar-attribution")
        assert resp.status_code == 200

    # -----------------------------------------------------------------------
    # 4. All 5 pillars present
    # -----------------------------------------------------------------------

    @patch(
        "routers.predictions.get_pillar_attribution",
        return_value=SAMPLE_PILLAR_ATTRIBUTION,
    )
    def test_pillar_attribution_has_all_pillars(self, _mock, authed_client):
        resp = authed_client.get("/api/v1/predictions/pillar-attribution")
        assert resp.status_code == 200
        data = resp.json()

        assert "pillars" in data
        returned_names = {p["pillar_name"] for p in data["pillars"]}
        assert returned_names == EXPECTED_PILLAR_NAMES, (
            f"Expected pillars {EXPECTED_PILLAR_NAMES}, got {returned_names}"
        )
        assert len(data["pillars"]) == 5

        # Each pillar must have the required attribution fields
        for pillar in data["pillars"]:
            assert "correlation_with_outcome" in pillar
            assert "bucketed_accuracy" in pillar
            assert isinstance(pillar["bucketed_accuracy"], list)
            assert "avg_brier_score" in pillar
            assert "predictive_lift" in pillar
            assert "missing_rate" in pillar
            assert isinstance(pillar["missing_rate"], (int, float))
            assert "usefulness_rank" in pillar


# ===========================================================================
# 5. Model versions endpoint — basic 200
# ===========================================================================

class TestModelVersionsEndpoint:

    @patch(
        "routers.predictions.get_model_version_analytics",
        return_value=SAMPLE_MODEL_VERSIONS,
    )
    def test_model_versions_endpoint_returns_200(self, _mock, authed_client):
        resp = authed_client.get("/api/v1/predictions/model-versions")
        assert resp.status_code == 200

    # -----------------------------------------------------------------------
    # 6. Model versions response schema
    # -----------------------------------------------------------------------

    @patch(
        "routers.predictions.get_model_version_analytics",
        return_value=SAMPLE_MODEL_VERSIONS,
    )
    def test_model_versions_response_schema(self, _mock, authed_client):
        resp = authed_client.get("/api/v1/predictions/model-versions")
        assert resp.status_code == 200
        data = resp.json()

        assert "versions" in data
        assert "total_predictions" in data
        assert isinstance(data["versions"], list)
        assert isinstance(data["total_predictions"], int)

        # Each version object must carry all required fields
        for v in data["versions"]:
            missing = MODEL_VERSION_REQUIRED_FIELDS - v.keys()
            assert not missing, f"Version object missing fields: {missing}"
            assert isinstance(v["model_version"], str)
            assert isinstance(v["total_predictions"], int)


# ===========================================================================
# 7. Empty database — graceful handling
# ===========================================================================

class TestCalibrationEmptyDB:

    @patch(
        "routers.predictions.get_calibration_metrics",
        return_value=EMPTY_CALIBRATION,
    )
    def test_calibration_empty_db(self, _mock, authed_client):
        """Calibration endpoint returns 200 with empty lists when DB has no predictions."""
        resp = authed_client.get("/api/v1/predictions/calibration")
        assert resp.status_code == 200
        data = resp.json()

        assert data["confidence_bucket_accuracy"] == []
        assert data["brier_score_by_bucket"] == []
        assert data["overconfidence_by_bucket"] == []
        assert data["hit_rate_by_horizon"] == []
        assert data["calibration_error"] is None
        assert data["expected_calibration_error"] is None
        assert data["max_calibration_error"] is None

    @patch(
        "routers.predictions.get_pillar_attribution",
        return_value=EMPTY_PILLAR_ATTRIBUTION,
    )
    def test_pillar_attribution_empty_db(self, _mock, authed_client):
        """Pillar attribution returns 200 with empty pillars list on empty DB."""
        resp = authed_client.get("/api/v1/predictions/pillar-attribution")
        assert resp.status_code == 200
        data = resp.json()

        assert data["pillars"] == []
        assert data["total_predictions"] == 0

    @patch(
        "routers.predictions.get_model_version_analytics",
        return_value=EMPTY_MODEL_VERSIONS,
    )
    def test_model_versions_empty_db(self, _mock, authed_client):
        """Model versions returns 200 with empty versions list on empty DB."""
        resp = authed_client.get("/api/v1/predictions/model-versions")
        assert resp.status_code == 200
        data = resp.json()

        assert data["versions"] == []
        assert data["total_predictions"] == 0


# ===========================================================================
# 8. Auth enforcement — 401 without token
# ===========================================================================

class TestEndpointsRequireAuth:

    def test_calibration_requires_auth(self, unauthed_client):
        resp = unauthed_client.get("/api/v1/predictions/calibration")
        assert resp.status_code == 401

    def test_pillar_attribution_requires_auth(self, unauthed_client):
        resp = unauthed_client.get("/api/v1/predictions/pillar-attribution")
        assert resp.status_code == 401

    def test_model_versions_requires_auth(self, unauthed_client):
        resp = unauthed_client.get("/api/v1/predictions/model-versions")
        assert resp.status_code == 401

    def test_invalid_bearer_token_returns_401(self, unauthed_client):
        resp = unauthed_client.get(
            "/api/v1/predictions/calibration",
            headers={"Authorization": "Bearer invalid_token_xyz"},
        )
        assert resp.status_code == 401
