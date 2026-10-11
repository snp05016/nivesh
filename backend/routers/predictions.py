"""
Prediction Performance & Calibration Endpoints
/api/v1/predictions/performance — comprehensive analytics dashboard
/api/v1/predictions/calibration — confidence calibration metrics
/api/v1/predictions/pillar-attribution — pillar-level predictive attribution
/api/v1/predictions/model-versions — model version comparison analytics
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, List

from helpers import require_auth
from core.security import require_admin
from services.predictions_performance import get_performance_metrics
from services.prediction_calibration_service import (
    get_calibration_metrics,
    get_pillar_attribution,
    get_model_version_analytics,
    get_calibration_health,
    get_fusion_weight_recommendations,
)
from schemas.prediction_calibration import (
    CalibrationBucket,
    CalibrationResponse,
    GroupCalibration,
    HorizonHitRate,
    ModelVersionsResponse,
    ModelVersionStats,
    PillarAttribution,
    PillarAttributionResponse,
    CalibrationHealthResponse,
    FusionWeightRecommendationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Response Schemas ──────────────────────────────────────────────

class HorizonPerformance(BaseModel):
    matured_count: int = 0
    hit_rate: Optional[float] = None
    avg_return: Optional[float] = None
    avg_brier_score: Optional[float] = None


class BucketPerformance(BaseModel):
    bucket_label: str
    count: int
    matured_count: Optional[int] = None
    hit_rate_30d: Optional[float] = None
    avg_return_30d: Optional[float] = None
    avg_brier_score_30d: Optional[float] = None


class GroupPerformance(BaseModel):
    group_key: str
    count: int
    hit_rate_30d: Optional[float] = None
    avg_return_30d: Optional[float] = None
    avg_brier_score_30d: Optional[float] = None


class PredictionsPerformanceResponse(BaseModel):
    total_predictions: int
    by_horizon: Dict[str, HorizonPerformance]
    confidence_buckets: List[BucketPerformance]
    by_scan_type: List[GroupPerformance]
    by_sector: List[GroupPerformance]
    by_regime: List[GroupPerformance]
    by_ml_engine_mode: List[GroupPerformance]
    by_recommendation: List[GroupPerformance]


# ── Endpoint ──────────────────────────────────────────────────────

@router.get(
    "/api/v1/predictions/performance",
    response_model=PredictionsPerformanceResponse,
    summary="Prediction Performance Dashboard",
    description="Returns aggregated performance metrics for all analysis predictions: "
    "hit rates by horizon, confidence calibration, and breakdowns by scan type, "
    "sector, market regime, ML engine mode, and recommendation direction.",
)
def get_predictions_performance(user_id: int = Depends(require_admin)):
    """
    Comprehensive performance analytics for all predictions in the system.

    Admin only (REG-11): hit rates of the app's own calls are an internal QA metric,
    not a sold feature or a user-facing performance claim (no PaRRVA verification).

    Args:
        user_id (int): The user_id.

    Returns:
        Any: The response.
    """
    data = get_performance_metrics()
    return PredictionsPerformanceResponse(
        total_predictions=data["total_predictions"],
        by_horizon={
            k: HorizonPerformance(**v) for k, v in data["by_horizon"].items()
        },
        confidence_buckets=[BucketPerformance(**b) for b in data["confidence_buckets"]],
        by_scan_type=[GroupPerformance(**g) for g in data["by_scan_type"]],
        by_sector=[GroupPerformance(**g) for g in data["by_sector"]],
        by_regime=[GroupPerformance(**g) for g in data["by_regime"]],
        by_ml_engine_mode=[GroupPerformance(**g) for g in data["by_ml_engine_mode"]],
        by_recommendation=[GroupPerformance(**g) for g in data["by_recommendation"]],
    )


# ── Calibration Endpoints ────────────────────────────────────────


@router.get(
    "/api/v1/predictions/calibration",
    response_model=CalibrationResponse,
    summary="Prediction Calibration Metrics",
    description="Returns confidence calibration analysis: bucket-level accuracy vs "
    "confidence, Brier scores, overconfidence metrics, expected/max calibration "
    "error, and breakdowns by scan type, regime, sector, ML engine mode, and "
    "recommendation direction.",
)
def get_predictions_calibration(
    user_id: int = Depends(require_auth),
    horizon: str = Query("30d", pattern="^(7|30|90)[dD]$"),
):
    """
    Confidence calibration analytics for all predictions.

    Args:
        user_id (int): The user_id.
        horizon (str): Outcome horizon to score against: 7d, 30d or 90d.

    Returns:
        Any: The response.
    """
    try:
        data = get_calibration_metrics(horizon=horizon.lower())

        def _to_bucket(b: dict) -> CalibrationBucket:
            return CalibrationBucket(
                bucket_label=b["bucket_label"],
                count=b["count"],
                accuracy=b.get("accuracy"),
                avg_brier_score=b.get("avg_brier_score_30d"),
                avg_confidence=b.get("avg_confidence_pct"),
                overconfidence=b.get("overconfidence"),
                total_count=b.get("total_count"),
                ci_low=b.get("ci_low"),
                ci_high=b.get("ci_high"),
                suppressed=b.get("suppressed"),
            )

        def _to_group(g: dict) -> GroupCalibration:
            return GroupCalibration(
                group_key=g["group_key"],
                count=g["count"],
                accuracy=g.get("accuracy"),
                avg_brier_score=g.get("avg_brier_score_30d"),
                avg_confidence=g.get("avg_confidence_pct"),
                calibration_error=g.get("calibration_error"),
            )

        buckets = [_to_bucket(b) for b in data.get("confidence_buckets", [])]
        horizon_dict = data.get("hit_rate_by_horizon", {})
        horizons = [
            HorizonHitRate(horizon=k, matured_count=v.get("matured_count", 0), hit_rate=v.get("hit_rate"))
            for k, v in horizon_dict.items()
        ]

        return CalibrationResponse(
            confidence_bucket_accuracy=buckets,
            brier_score_by_bucket=buckets,
            overconfidence_by_bucket=buckets,
            calibration_error=data.get("calibration_error"),
            expected_calibration_error=data.get("expected_calibration_error"),
            max_calibration_error=data.get("max_calibration_error"),
            hit_rate_by_horizon=horizons,
            calibration_by_scan_type=[_to_group(g) for g in data.get("calibration_by_scan_type", [])],
            calibration_by_regime=[_to_group(g) for g in data.get("calibration_by_regime", [])],
            calibration_by_sector=[_to_group(g) for g in data.get("calibration_by_sector", [])],
            calibration_by_ml_engine_mode=[_to_group(g) for g in data.get("calibration_by_ml_engine_mode", [])],
            calibration_by_recommendation=[_to_group(g) for g in data.get("calibration_by_recommendation", [])],
        )
    except Exception as e:
        import logging
        logging.warning(f"Caught exception: {e}")
        logger.exception("Failed to compute calibration metrics")
        raise HTTPException(status_code=500, detail="Internal error computing calibration metrics")


@router.get(
    "/api/v1/predictions/pillar-attribution",
    response_model=PillarAttributionResponse,
    summary="Pillar-Level Predictive Attribution",
    description="Returns per-pillar (technical, fundamental, sentiment, macro, etc.) "
    "attribution metrics: correlation with outcome, bucketed accuracy, Brier score, "
    "predictive lift over final confidence, missing rate, and usefulness ranking.",
)
def get_predictions_pillar_attribution(user_id: int = Depends(require_auth)):
    """
    Pillar-level attribution analytics showing which analysis pillars are most predictive.

    Args:
        user_id (int): The user_id.

    Returns:
        Any: The response.
    """
    try:
        data = get_pillar_attribution()
        pillars_dict = data.get("pillars", {})
        pillar_list = []
        for name, info in pillars_dict.items():
            bucketed = [
                CalibrationBucket(
                    bucket_label=b.get("range", ""),
                    count=b.get("count", 0),
                    accuracy=b.get("hit_rate"),
                )
                for b in info.get("bucketed_accuracy", [])
            ]
            pillar_list.append(PillarAttribution(
                pillar_name=name,
                correlation_with_outcome=info.get("correlation_with_hit_30d"),
                bucketed_accuracy=bucketed,
                avg_brier_score=info.get("avg_brier_score_30d"),
                predictive_lift=info.get("predictive_lift"),
                missing_rate=info.get("missing_rate", 0.0),
                usefulness_rank=info.get("usefulness_rank"),
            ))
        return PillarAttributionResponse(
            pillars=pillar_list,
            total_predictions=data.get("total_predictions", 0),
        )
    except Exception as e:
        import logging
        logging.warning(f"Caught exception: {e}")
        logger.exception("Failed to compute pillar attribution")
        raise HTTPException(status_code=500, detail="Internal error computing pillar attribution")


@router.get(
    "/api/v1/predictions/model-versions",
    response_model=ModelVersionsResponse,
    summary="Model Version Comparison Analytics",
    description="Returns performance metrics grouped by model version and ML engine mode: "
    "hit rates across horizons, average returns, Brier scores, calibration error, "
    "and the gap between stated confidence and realized accuracy.",
)
def get_predictions_model_versions(user_id: int = Depends(require_auth)):
    """
    Model version comparison analytics across all prediction horizons.

    Args:
        user_id (int): The user_id.

    Returns:
        Any: The response.
    """
    try:
        data = get_model_version_analytics()
        versions = [
            ModelVersionStats(**v) for v in data.get("model_versions", [])
        ]
        return ModelVersionsResponse(
            versions=versions,
            total_predictions=data.get("total_predictions", 0),
        )
    except Exception as e:
        import logging
        logging.warning(f"Caught exception: {e}")
        logger.exception("Failed to compute model version analytics")
        raise HTTPException(status_code=500, detail="Internal error computing model version analytics")


@router.get(
    "/api/v1/predictions/calibration/health",
    response_model=CalibrationHealthResponse,
    summary="Calibration Data Health",
    description="Returns data readiness counts to determine if enough matured predictions exist for reliable fusion weight calibration.",
)
def get_calibration_readiness_health(user_id: int = Depends(require_auth)):
    """
    Check if the system has enough prediction outcomes to calibrate confidence fusion.

    Args:
        user_id (int): The user_id.

    Returns:
        Any: The response.
    """
    try:
        data = get_calibration_health()
        return CalibrationHealthResponse(**data)
    except Exception as e:
        import logging
        logging.warning(f"Caught exception: {e}")
        logger.exception("Failed to compute calibration health")
        raise HTTPException(status_code=500, detail="Internal error computing calibration health")


@router.get(
    "/api/v1/predictions/fusion-weight-recommendations",
    response_model=FusionWeightRecommendationResponse,
    summary="Fusion Weight Recommendations",
    description="Returns advisory confidence fusion weights based on historical pillar performance. Never mutates code automatically.",
)
def get_fusion_weight_recommendations_endpoint(user_id: int = Depends(require_auth)):
    """
    Generates recommended weights for prediction confidence fusion based on historical performance.

    Args:
        user_id (int): The user_id.

    Returns:
        Any: The response.
    """
    try:
        data = get_fusion_weight_recommendations()
        return FusionWeightRecommendationResponse(**data)
    except Exception as e:
        import logging
        logging.warning(f"Caught exception: {e}")
        logger.exception("Failed to compute fusion weight recommendations")
        raise HTTPException(status_code=500, detail="Internal error computing fusion weight recommendations")
