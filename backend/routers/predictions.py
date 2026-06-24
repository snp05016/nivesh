"""
Prediction Performance Endpoints
/api/v1/predictions/performance — comprehensive analytics dashboard
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, List

from helpers import require_auth
from services.predictions_performance import get_performance_metrics

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
def get_predictions_performance(user_id: int = Depends(require_auth)):
    """Comprehensive performance analytics for all predictions in the system."""
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
