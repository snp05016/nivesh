from pydantic import BaseModel
from typing import List, Optional


class FeatureDriver(BaseModel):
    feature: str
    contribution: float
    direction: str  # "positive" or "negative"


class MLReliability(BaseModel):
    hit_rate_30d: Optional[float] = None
    brier_score_30d: Optional[float] = None
    calibration_error_30d: Optional[float] = None


class MLSignalResponse(BaseModel):
    symbol: str
    direction: int  # 1=bullish, -1=bearish, 0=neutral
    direction_label: str  # "BULLISH", "BEARISH", "NEUTRAL"
    confidence: Optional[float] = None
    confidence_pct: Optional[int] = None
    model_version: Optional[str] = None
    model_status: Optional[str] = None
    ml_engine_mode: str
    lightgbm_loaded: bool = False
    prediction_horizon: str = "20d"
    generated_at: str
    feature_drivers: List[FeatureDriver] = []
    reliability: Optional[MLReliability] = None
    status: str  # "ready", "unavailable", "error"
    warning: Optional[str] = None
