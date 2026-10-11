"""
Tests for /api/v1/predictions/performance endpoint.
Covers schema validation, empty state, populated data, and edge cases.

Uses the stockapp_test.db configured by conftest (file-based SQLite, shared
across sessions so test seeding and the API handler can see the same data).
"""
import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from database import get_session, create_access_token, User
from models.db_models import AnalysisPrediction, StockUniverse
from services import subscription_service


@pytest.fixture(scope="module")
def pro_headers():
    """JWT of a throwaway pro-tier user: the endpoint is gated on advanced_analysis and
    there is no admin token bypass (AUTH-02). Throwaway, so the tier never leaks."""
    with get_session() as session:
        user = User(username=f"perf_pro_{uuid4().hex[:12]}", password_hash="x", display_name="Perf Pro")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    subscription_service.mock_upgrade(user_id, "pro", "monthly")
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _seed(session):
    """Insert stock universe and prediction rows into the shared test DB."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    sectors = [
        ("TCS.NS_88001", "Information Technology"),
        ("RELIANCE.NS_88002", "Oil & Gas"),
        ("HDFCBANK.NS_88003", "Financial Services"),
        ("TATAMOTORS.NS_88004", "Automobile"),
    ]
    for ticker, sector in sectors:
        session.add(StockUniverse(ticker=ticker, company_name=ticker, sector=sector))

    predictions = [
        ("TCS.NS_88001", "BULLISH", 85, "standard", "trending_bull",
         "lgbm_trained", 0.045, True, 0.0225, 0.012, True, 0.0225, 0.12, True, 0.0225),
        ("TCS.NS_88001", "BULLISH", 55, "deep", "ranging",
         "lgbm_trained", -0.02, False, 0.3025, 0.005, True, 0.2025, None, None, None),
        ("RELIANCE.NS_88002", "BEARISH", 70, "standard", "volatile",
         "fallback_technical_heuristic", -0.035, True, 0.09, -0.01, True, 0.09, None, None, None),
        ("HDFCBANK.NS_88003", "HOLD", 50, "standard", None,
         "lgbm_trained", 0.01, None, None, None, None, None, None, None, None),
        ("TATAMOTORS.NS_88004", "BEARISH", 90, "extreme", "trending_bear",
         "fallback_technical_heuristic", -0.08, True, 0.01, -0.03, True, 0.01, None, None, None),
    ]

    seeded_ids = []
    for row in predictions:
        (sym, rec, conf, st, regime, ml_mode,
         ret30, hit30, brier30, ret7, hit7, brier7, ret90, hit90, brier90) = row
        pred = AnalysisPrediction(
            symbol=sym, recommendation=rec, confidence_pct=conf,
            scan_type=st, regime_id=regime, ml_engine_mode=ml_mode,
            created_at=now - timedelta(days=60 + len(seeded_ids)),
            horizon_days=30, entry_price=1000.0, target_price=1200.0,
            actual_return_30d=ret30, hit_direction_30d=hit30, brier_score_30d=brier30,
            actual_return_7d=ret7, hit_direction_7d=hit7, brier_score_7d=brier7,
            actual_return_90d=ret90, hit_direction_90d=hit90, brier_score_90d=brier90,
        )
        session.add(pred)
        session.flush()  # get auto-assigned id
        seeded_ids.append(pred.id)

    session.commit()
    return seeded_ids, [s[0] for s in sectors]


def _cleanup(session, pred_ids, tickers):
    """Remove only the rows we seeded."""
    try:
        if pred_ids:
            session.query(AnalysisPrediction).filter(
                AnalysisPrediction.id.in_(pred_ids)
            ).delete(synchronize_session=False)
        if tickers:
            session.query(StockUniverse).filter(
                StockUniverse.ticker.in_(tickers)
            ).delete(synchronize_session=False)
        session.commit()
    except Exception as _e:
        session.rollback()


class TestEmptyPerformance:
    def test_empty_db_returns_zeros(self, client, pro_headers):
        """When no predictions exist for our test tickers, totals should reflect system state."""
        resp = client.get("/api/v1/predictions/performance", headers=pro_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "total_predictions" in body
        for h in ["7d", "30d", "90d"]:
            assert "matured_count" in body["by_horizon"][h]

    def test_auth_required(self, client):
        resp = client.get("/api/v1/predictions/performance")
        assert resp.status_code == 401


class TestPopulatedPerformance:
    @pytest.fixture(autouse=True)
    def seed_and_cleanup(self, client, pro_headers):
        # The DB is shared with other modules, so assert on the delta our seed adds.
        self.before = client.get("/api/v1/predictions/performance", headers=pro_headers).json()
        with get_session() as session:
            self.pred_ids, tickers = _seed(session)
        yield
        with get_session() as session:
            _cleanup(session, self.pred_ids, tickers)

    @pytest.fixture
    def response(self, client, pro_headers):
        return client.get("/api/v1/predictions/performance", headers=pro_headers)

    def test_total_predictions_includes_seeded(self, response):
        assert response.status_code == 200
        body = response.json()
        assert body["total_predictions"] == self.before["total_predictions"] + len(self.pred_ids)

    def test_response_schema(self, response):
        body = response.json()
        for key in ["total_predictions", "by_horizon", "confidence_buckets",
                    "by_scan_type", "by_sector", "by_regime",
                    "by_ml_engine_mode", "by_recommendation"]:
            assert key in body, f"Missing key: {key}"

    def test_confidence_bucket_schema(self, response):
        body = response.json()
        # Same bucket scheme as the calibration endpoint (ML-14).
        from services.prediction_calibration_service import CONFIDENCE_BUCKETS
        labels = [b["bucket_label"] for b in body["confidence_buckets"]]
        assert labels == [label for _, _, label in CONFIDENCE_BUCKETS]
        for b in body["confidence_buckets"]:
            assert b["matured_count"] <= b["count"]

    def test_by_scan_type_has_expected_keys(self, response):
        body = response.json()
        types = [g["group_key"] for g in body["by_scan_type"]]
        for t in ["standard", "deep", "extreme"]:
            assert t in types, f"Expected '{t}' in by_scan_type"

    def test_by_recommendation_has_keys(self, response):
        body = response.json()
        recs = [g["group_key"] for g in body["by_recommendation"]]
        for r in ["BULLISH", "BEARISH", "HOLD"]:
            assert r in recs, f"Expected '{r}' in by_recommendation"

    def test_by_ml_engine_mode_has_keys(self, response):
        body = response.json()
        modes = [g["group_key"] for g in body["by_ml_engine_mode"]]
        for m in ["lgbm_trained", "fallback_technical_heuristic"]:
            assert m in modes, f"Expected '{m}' in by_ml_engine_mode"

    def test_by_sector_has_expected_keys(self, response):
        body = response.json()
        sectors = [g["group_key"] for g in body["by_sector"]]
        for s in ["Information Technology", "Oil & Gas", "Financial Services", "Automobile"]:
            assert s in sectors, f"Expected '{s}' in by_sector"

    def test_horizon_stats_numeric(self, response):
        """Hit rates and returns should be numeric or None (never error strings)."""
        body = response.json()
        for h in ["7d", "30d", "90d"]:
            hp = body["by_horizon"][h]
            assert isinstance(hp["matured_count"], int)
            if hp["hit_rate"] is not None:
                assert 0.0 <= hp["hit_rate"] <= 1.0
            if hp["avg_brier_score"] is not None:
                assert hp["avg_brier_score"] >= 0.0

    def test_group_performance_fields(self, response):
        body = response.json()
        for key in ["by_scan_type", "by_regime", "by_ml_engine_mode",
                    "by_recommendation", "by_sector"]:
            for g in body[key]:
                assert "group_key" in g
                assert "count" in g
                assert isinstance(g["count"], int)
                assert g["count"] > 0
                if g["hit_rate_30d"] is not None:
                    assert 0.0 <= g["hit_rate_30d"] <= 1.0

    def test_confidence_buckets_add_exactly_seeded(self, response):
        body = response.json()
        total_in_buckets = sum(b["count"] for b in body["confidence_buckets"])
        before_in_buckets = sum(b["count"] for b in self.before["confidence_buckets"])
        assert total_in_buckets == before_in_buckets + len(self.pred_ids)


class TestEdgeCases:
    def test_prediction_no_outcome_yet(self, client, pro_headers):
        """A prediction with no outcome should appear in totals but hit_rate is None."""
        with get_session() as session:
            session.add(AnalysisPrediction(
                symbol="TEST_FRESH.NS_88100", recommendation="BULLISH",
                confidence_pct=60, scan_type="standard",
            ))
            session.commit()

        resp = client.get("/api/v1/predictions/performance", headers=pro_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_predictions"] >= 1

        # Cleanup
        with get_session() as session:
            from sqlalchemy import text
            session.execute(text("DELETE FROM analysis_predictions WHERE symbol='TEST_FRESH.NS_88100'"))
            session.commit()
