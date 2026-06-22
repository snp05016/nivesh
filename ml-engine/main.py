"""
ml-engine FastAPI microservice — standalone inference server (port 8001).

Provides ML predictions to the Nivesh backend (Python 3.14) which cannot
run Qlib/LightGBM natively due to Python version constraints.

Endpoints:
  GET  /health                    — liveness probe
  POST /predict/cross-section     — batch prediction for multiple stocks
  POST /predict/single            — single-stock prediction from OHLCV data
  GET  /model/status              — loaded model metadata

Lifecycle:
  startup  -> loads LightGBM model + TRA model + feature scaler
  shutdown -> releases GPU memory, closes model handles
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from config import (
    LIGHTGBM_MODEL_PATH,
    TRA_MODEL_PATH,
    SCALER_PATH,
    FEATURE_LIST,
    REGIME_THRESHOLDS,
    CONFIDENCE_CONFIG,
    LIGHTGBM_PARAMS,
)
from models.model_loader import ModelLoader
from pipeline.feature_computer import FeatureComputer
from pipeline.inference import InferenceEngine

_LOG = logging.getLogger("ml-engine")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

# ── Globals (initialized at startup, use with caution — read-only after loading) ──

_lightgbm_model: Any = None
_tra_model: Any = None
_feature_scaler: dict[str, dict[str, float]] | None = None
_feature_computer: FeatureComputer | None = None
_inference_engine: InferenceEngine | None = None


# ── Request / Response Models ──────────────────────────────────────────────────


class OHLCVRow(BaseModel):
    """Single day of OHLCV data."""
    date: str | None = None
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float | None = None


class CrossSectionRequest(BaseModel):
    """Batch prediction request — array of OHLCV arrays, one per stock."""
    stocks: list[list[OHLCVRow]] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="List of OHLCV sequences, one per stock",
    )
    model_type: str = Field(
        default="lightgbm",
        pattern="^(lightgbm|tra|ensemble)$",
        description="Which model to use for prediction",
    )


class SingleStockRequest(BaseModel):
    """Single-stock prediction request."""
    ohlcv: list[OHLCVRow] = Field(
        default_factory=list,
        min_length=0,
        max_length=500,
        description="OHLCV data — 60+ rows recommended, minimum 5",
        alias="ohlcv",
    )
    ohlcv_data: list[OHLCVRow] = Field(
        default_factory=list,
        min_length=0,
        max_length=500,
        description="OHLCV data (alternate key from Nivesh orchestrator)",
    )
    ticker: str = Field(default="UNKNOWN", description="Stock ticker for logging")
    model_type: str = Field(
        default="lightgbm",
        pattern="^(lightgbm|tra|ensemble)$",
    )


class PredictionResult(BaseModel):
    """Prediction result for a single stock."""
    ticker: str = ""
    expected_direction: int = Field(
        ...,
        ge=-1,
        le=1,
        description="-1 (bearish), 0 (neutral), 1 (bullish)",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Calibrated confidence (0-1)",
    )
    features: list[str] = Field(
        default_factory=list,
        description="Feature names used for prediction",
    )
    prediction_time_ms: float = Field(
        ...,
        description="Inference wall-clock time in milliseconds",
    )
    raw_score: float | None = Field(
        default=None,
        description="Raw model score before thresholding",
    )


class CrossSectionResponse(BaseModel):
    """Batch prediction response."""
    predictions: list[PredictionResult]
    total_time_ms: float
    model_used: str


class ModelStatus(BaseModel):
    """Model metadata response."""
    lightgbm_loaded: bool
    tra_loaded: bool
    scaler_loaded: bool
    feature_count: int
    lightgbm_path: str | None = None


# ── Lifespan ───────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Load models and scaler at startup; clean up at shutdown."""
    global _lightgbm_model, _tra_model, _feature_scaler
    global _feature_computer, _inference_engine

    _LOG.info("ml-engine starting up — loading models...")

    # LightGBM
    try:
        _lightgbm_model = ModelLoader.load_lightgbm(LIGHTGBM_MODEL_PATH)
        _LOG.info("LightGBM model loaded from %s", LIGHTGBM_MODEL_PATH)
    except FileNotFoundError:
        _LOG.warning(
            "LightGBM model not found at %s — prediction will use fallback heuristic",
            LIGHTGBM_MODEL_PATH,
        )
        _lightgbm_model = None

    # TRA PyTorch model
    try:
        _tra_model = ModelLoader.load_tra(TRA_MODEL_PATH)
        _LOG.info("TRA model loaded from %s", TRA_MODEL_PATH)
    except FileNotFoundError:
        _LOG.warning(
            "TRA model not found at %s — sequence prediction disabled",
            TRA_MODEL_PATH,
        )
        _tra_model = None

    # Feature scaler
    try:
        _feature_scaler = ModelLoader.load_scaler(SCALER_PATH)
        _LOG.info("Feature scaler loaded from %s", SCALER_PATH)
    except FileNotFoundError:
        _LOG.warning(
            "Feature scaler not found at %s — using identity scaling",
            SCALER_PATH,
        )
        _feature_scaler = None

    _feature_computer = FeatureComputer(
        feature_list=FEATURE_LIST,
        scaler_params=_feature_scaler,
    )
    _inference_engine = InferenceEngine(
        lightgbm_model=_lightgbm_model,
        tra_model=_tra_model,
        lgb_params=LIGHTGBM_PARAMS,
        regime_thresholds=REGIME_THRESHOLDS,
        confidence_config=CONFIDENCE_CONFIG,
    )

    _LOG.info("ml-engine ready — listening on port 8001")
    yield

    _LOG.info("ml-engine shutting down — releasing model resources")
    _lightgbm_model = None
    _tra_model = None
    _feature_scaler = None


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Nivesh ML Engine",
    description=(
        "Standalone inference microservice — LightGBM + TRA models "
        "with Alpha158 features for Indian equity prediction"
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# ── Health ─────────────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": "ml-engine"}


# ── Model Status ───────────────────────────────────────────────────────────────


@app.get("/model/status", response_model=ModelStatus)
async def model_status() -> ModelStatus:
    """Return loaded model metadata."""
    return ModelStatus(
        lightgbm_loaded=_lightgbm_model is not None,
        tra_loaded=_tra_model is not None,
        scaler_loaded=_feature_scaler is not None,
        feature_count=len(FEATURE_LIST),
        lightgbm_path=str(LIGHTGBM_MODEL_PATH) if _lightgbm_model else None,
    )


# ── Prediction Helpers ─────────────────────────────────────────────────────────


def _ohlcv_to_polars(rows: list[OHLCVRow]) -> pl.DataFrame:
    """Convert Pydantic OHLCV rows to a Polars DataFrame."""
    records = []
    for r in rows:
        vwap_value = r.vwap if r.vwap is not None else (r.high + r.low + r.close) / 3.0
        records.append({
            "date": r.date,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "volume": r.volume,
            "vwap": vwap_value,
        })
    return pl.DataFrame(records)


# ── Predict ────────────────────────────────────────────────────────────────────


@app.post("/predict/single", response_model=PredictionResult)
async def predict_single(req: SingleStockRequest) -> PredictionResult:
    """Predict for a single stock from its OHLCV history."""
    if _feature_computer is None or _inference_engine is None:
        raise HTTPException(status_code=503, detail="Model engine not initialized")

    t0 = time.perf_counter()

    df = _ohlcv_to_polars(req.ohlcv_data or req.ohlcv)

    try:
        features_df = _feature_computer.compute_all(df)
    except Exception as exc:
        _LOG.error("Feature computation failed for %s: %s", req.ticker, exc)
        raise HTTPException(status_code=422, detail=f"Feature computation failed: {exc}")

    try:
        result = _inference_engine.predict(
            features_df,
            ticker=req.ticker,
            model_type=req.model_type,
        )
    except Exception as exc:
        _LOG.error("Inference failed for %s: %s", req.ticker, exc)
        raise HTTPException(status_code=500, detail=f"Inference failed: {exc}")

    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    return PredictionResult(
        ticker=req.ticker,
        expected_direction=result["expected_direction"],
        confidence_score=result["confidence_score"],
        features=FEATURE_LIST[:20],  # first 20 feature names as context
        prediction_time_ms=round(elapsed_ms, 2),
        raw_score=result.get("raw_score"),
    )


@app.post("/predict/cross-section", response_model=CrossSectionResponse)
async def predict_cross_section(req: CrossSectionRequest) -> CrossSectionResponse:
    """Batch prediction across multiple stocks."""
    if _feature_computer is None or _inference_engine is None:
        raise HTTPException(status_code=503, detail="Model engine not initialized")

    t0 = time.perf_counter()
    predictions: list[PredictionResult] = []

    for i, ohlcv_rows in enumerate(req.stocks):
        ticker = f"stock_{i}"
        try:
            df = _ohlcv_to_polars(ohlcv_rows)
            features_df = _feature_computer.compute_all(df)
            result = _inference_engine.predict(
                features_df,
                ticker=ticker,
                model_type=req.model_type,
            )
            predictions.append(
                PredictionResult(
                    ticker=ticker,
                    expected_direction=result["expected_direction"],
                    confidence_score=result["confidence_score"],
                    features=FEATURE_LIST[:20],
                    prediction_time_ms=0.0,  # individual timings not meaningful in batch
                    raw_score=result.get("raw_score"),
                )
            )
        except Exception as exc:
            _LOG.warning("Prediction failed for %s: %s", ticker, exc)
            predictions.append(
                PredictionResult(
                    ticker=ticker,
                    expected_direction=0,
                    confidence_score=0.0,
                    features=[],
                    prediction_time_ms=0.0,
                    raw_score=None,
                )
            )

    total_ms = (time.perf_counter() - t0) * 1000.0
    return CrossSectionResponse(
        predictions=predictions,
        total_time_ms=round(total_ms, 2),
        model_used=req.model_type,
    )
