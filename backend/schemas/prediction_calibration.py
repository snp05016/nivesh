"""Prediction calibration and pillar attribution response schemas."""

from typing import List, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

class CalibrationBucket(BaseModel):
    bucket_label: str
    count: int
    accuracy: Optional[float] = None
    avg_brier_score: Optional[float] = None
    avg_confidence: Optional[float] = None
    overconfidence: Optional[float] = None  # avg_confidence - accuracy, null if either missing


class HorizonHitRate(BaseModel):
    horizon: str  # "7d" | "30d" | "90d"
    matured_count: int
    hit_rate: Optional[float] = None


class GroupCalibration(BaseModel):
    group_key: str
    count: int
    accuracy: Optional[float] = None
    avg_brier_score: Optional[float] = None
    avg_confidence: Optional[float] = None
    calibration_error: Optional[float] = None


class CalibrationResponse(BaseModel):
    confidence_bucket_accuracy: List[CalibrationBucket]
    brier_score_by_bucket: List[CalibrationBucket]
    overconfidence_by_bucket: List[CalibrationBucket]
    calibration_error: Optional[float] = None  # overall
    expected_calibration_error: Optional[float] = None
    max_calibration_error: Optional[float] = None
    hit_rate_by_horizon: List[HorizonHitRate]
    calibration_by_scan_type: List[GroupCalibration]
    calibration_by_regime: List[GroupCalibration]
    calibration_by_sector: List[GroupCalibration]
    calibration_by_ml_engine_mode: List[GroupCalibration]
    calibration_by_recommendation: List[GroupCalibration]


# ---------------------------------------------------------------------------
# Pillar Attribution
# ---------------------------------------------------------------------------

class PillarAttribution(BaseModel):
    pillar_name: str
    correlation_with_outcome: Optional[float] = None
    bucketed_accuracy: List[CalibrationBucket]
    avg_brier_score: Optional[float] = None
    predictive_lift: Optional[float] = None  # how much better this pillar is vs final confidence
    missing_rate: float
    usefulness_rank: Optional[int] = None


class PillarAttributionResponse(BaseModel):
    pillars: List[PillarAttribution]
    total_predictions: int


# ---------------------------------------------------------------------------
# Model Version Comparison
# ---------------------------------------------------------------------------

class ModelVersionStats(BaseModel):
    model_version: str
    ml_engine_mode: Optional[str] = None
    total_predictions: int
    hit_rate_7d: Optional[float] = None
    hit_rate_30d: Optional[float] = None
    hit_rate_90d: Optional[float] = None
    average_return_30d: Optional[float] = None
    brier_score_30d: Optional[float] = None
    calibration_error_30d: Optional[float] = None
    confidence_avg: Optional[float] = None
    confidence_realized_accuracy_gap: Optional[float] = None


class ModelVersionsResponse(BaseModel):
    versions: List[ModelVersionStats]
    total_predictions: int
