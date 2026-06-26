"""Prediction calibration and pillar attribution response schemas."""

from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

class CalibrationBucket(BaseModel):
    """Bucket for prediction calibration metrics."""
    bucket_label: str = Field(..., description="Label for the confidence bucket")
    count: int = Field(..., description="Number of predictions in this bucket")
    accuracy: Optional[float] = Field(None, description="Actual realized accuracy")
    avg_brier_score: Optional[float] = Field(None, description="Average Brier score")
    avg_confidence: Optional[float] = Field(None, description="Average model confidence")
    overconfidence: Optional[float] = Field(None, description="Difference between confidence and accuracy")


class HorizonHitRate(BaseModel):
    """Hit rate metrics for a specific time horizon."""
    horizon: str = Field(..., description="Time horizon (e.g., '7d', '30d')")
    matured_count: int = Field(..., description="Number of matured predictions")
    hit_rate: Optional[float] = Field(None, description="Directional hit rate percentage")


class GroupCalibration(BaseModel):
    """Calibration metrics grouped by a specific key."""
    group_key: str = Field(..., description="Key for the group (e.g., sector name)")
    count: int = Field(..., description="Number of predictions in group")
    accuracy: Optional[float] = Field(None, description="Realized accuracy")
    avg_brier_score: Optional[float] = Field(None, description="Average Brier score")
    avg_confidence: Optional[float] = Field(None, description="Average confidence")
    calibration_error: Optional[float] = Field(None, description="Calibration error for group")


class CalibrationResponse(BaseModel):
    """Aggregated calibration metrics response."""
    confidence_bucket_accuracy: List[CalibrationBucket] = Field(..., description="Accuracy by confidence bucket")
    brier_score_by_bucket: List[CalibrationBucket] = Field(..., description="Brier score by bucket")
    overconfidence_by_bucket: List[CalibrationBucket] = Field(..., description="Overconfidence by bucket")
    calibration_error: Optional[float] = Field(None, description="Overall calibration error")
    expected_calibration_error: Optional[float] = Field(None, description="Expected calibration error (ECE)")
    max_calibration_error: Optional[float] = Field(None, description="Maximum calibration error (MCE)")
    hit_rate_by_horizon: List[HorizonHitRate] = Field(..., description="Hit rate grouped by horizon")
    calibration_by_scan_type: List[GroupCalibration] = Field(..., description="Calibration grouped by scan type")
    calibration_by_regime: List[GroupCalibration] = Field(..., description="Calibration grouped by market regime")
    calibration_by_sector: List[GroupCalibration] = Field(..., description="Calibration grouped by sector")
    calibration_by_ml_engine_mode: List[GroupCalibration] = Field(..., description="Calibration grouped by ML mode")
    calibration_by_recommendation: List[GroupCalibration] = Field(..., description="Calibration grouped by recommendation")


# ---------------------------------------------------------------------------
# Pillar Attribution
# ---------------------------------------------------------------------------

class PillarAttribution(BaseModel):
    """Attribution metrics for a specific analysis pillar."""
    pillar_name: str = Field(..., description="Name of the analysis pillar")
    correlation_with_outcome: Optional[float] = Field(None, description="Correlation with actual outcome")
    bucketed_accuracy: List[CalibrationBucket] = Field(..., description="Accuracy by confidence bucket for this pillar")
    avg_brier_score: Optional[float] = Field(None, description="Average Brier score for this pillar")
    predictive_lift: Optional[float] = Field(None, description="Predictive lift versus baseline")
    missing_rate: float = Field(..., description="Percentage of times this pillar is missing")
    usefulness_rank: Optional[int] = Field(None, description="Rank of pillar usefulness")


class PillarAttributionResponse(BaseModel):
    """Response containing pillar attributions."""
    pillars: List[PillarAttribution] = Field(..., description="List of pillar attributions")
    total_predictions: int = Field(..., description="Total number of predictions analyzed")


# ---------------------------------------------------------------------------
# Model Version Comparison
# ---------------------------------------------------------------------------

class ModelVersionStats(BaseModel):
    """Performance statistics for a specific model version."""
    model_version: str = Field(..., description="Model version identifier")
    ml_engine_mode: Optional[str] = Field(None, description="ML engine mode used")
    total_predictions: int = Field(..., description="Total predictions by this version")
    hit_rate_7d: Optional[float] = Field(None, description="7-day hit rate")
    hit_rate_30d: Optional[float] = Field(None, description="30-day hit rate")
    hit_rate_90d: Optional[float] = Field(None, description="90-day hit rate")
    average_return_30d: Optional[float] = Field(None, description="Average 30-day return")
    brier_score_30d: Optional[float] = Field(None, description="30-day Brier score")
    calibration_error_30d: Optional[float] = Field(None, description="30-day calibration error")
    confidence_avg: Optional[float] = Field(None, description="Average model confidence")
    confidence_realized_accuracy_gap: Optional[float] = Field(None, description="Gap between confidence and accuracy")


class ModelVersionsResponse(BaseModel):
    """Response containing stats for all model versions."""
    versions: List[ModelVersionStats] = Field(..., description="List of model version statistics")
    total_predictions: int = Field(..., description="Total predictions across all versions")


# ---------------------------------------------------------------------------
# Calibration Health
# ---------------------------------------------------------------------------

class CalibrationHealthResponse(BaseModel):
    """Health check response for calibration engine."""
    total_predictions: int = Field(..., description="Total stored predictions")
    matured_7d: int = Field(..., description="Predictions matured past 7 days")
    matured_30d: int = Field(..., description="Predictions matured past 30 days")
    matured_90d: int = Field(..., description="Predictions matured past 90 days")
    latest_prediction_date: Optional[str] = Field(None, description="Date of most recent prediction")
    is_ready_for_calibration: bool = Field(..., description="Whether enough data exists to run calibration")
    warnings: List[str] = Field(..., description="Warnings about data quality or volume")


# ---------------------------------------------------------------------------
# Fusion Weight Recommendations
# ---------------------------------------------------------------------------

class FusionWeightRecommendationResponse(BaseModel):
    """Recommendations for confidence fusion weights."""
    recommended_weights: dict = Field(..., description="Suggested weights for each component")
    warnings: List[str] = Field(..., description="Warnings about the recommendations")
    apply_recommendation: bool = Field(..., description="Whether to automatically apply recommendations")
    is_confident: bool = Field(..., description="Whether the engine is confident in the recommendations")

