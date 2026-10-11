"""
ml-engine FastAPI microservice — standalone inference server (port 8001).

Provides ML predictions to the Nivesh backend (Python 3.14) which cannot
run Qlib/LightGBM natively due to Python version constraints.

Endpoints:
  GET  /health                    — liveness probe
  POST /predict/single            — single-stock prediction from OHLCV data
  GET  /model/status              — loaded model metadata

/predict/single and /model/status require the ``X-ML-Engine-Key`` header when
ML_ENGINE_API_KEY is set (the backend sends it); /health stays open for probes.

Only the LightGBM booster is served: model_type accepts "lightgbm" alone
(no TRA weights ship, so "tra"/"ensemble" are rejected with 422).

Lifecycle:
  startup  -> loads LightGBM model + feature scaler
  shutdown -> releases model handles
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from config import (
    LIGHTGBM_MODEL_PATH,
    SCALER_PATH,
    FEATURE_LIST,
    CONFIDENCE_CONFIG,
    LIGHTGBM_PARAMS,
)
from models.model_loader import ModelLoader
from pipeline.feature_computer import (
    FeatureComputer,
    InsufficientHistoryError,
    InvalidOHLCVError,
)
from pipeline.inference import InferenceEngine
from research.api import router as research_router

_LOG = logging.getLogger("ml-engine")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

# ── Globals (initialized at startup, use with caution — read-only after loading) ──

_lightgbm_model: Any = None
_feature_scaler: dict[str, dict[str, float]] | None = None
_feature_computer: FeatureComputer | None = None
_inference_engine: InferenceEngine | None = None
_model_version: str | None = None
_model_validated: bool = False

# Written at promotion time; records the gate result, base rate and neutral band.
MANIFEST_PATH = LIGHTGBM_MODEL_PATH.parent / "MANIFEST.json"

SUPPORTED_HORIZONS = [20]
DEFAULT_PREDICTION_HORIZON = 20
# Reject inputs whose latest bar is older than this (calendar days, covers
# long exchange holidays): a stale series would be scored as if it were current.
MAX_INPUT_AGE_DAYS = 10


def require_api_key(x_ml_engine_key: str | None = Header(default=None)) -> None:
    """Reject callers without the shared secret when ML_ENGINE_API_KEY is set.

    ponytail: unset key = open (local dev); the loopback-only port publish is the
    primary control, this is defence in depth for anything else on the host.
    """
    expected = os.getenv("ML_ENGINE_API_KEY")
    if expected and not hmac.compare_digest((x_ml_engine_key or "").encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")


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


class SingleStockRequest(BaseModel):
    """Single-stock prediction request."""
    ohlcv: list[OHLCVRow] = Field(
        default_factory=list,
        min_length=0,
        max_length=500,
        description="OHLCV data — minimum 60 rows (longest feature window)",
        alias="ohlcv",
    )
    ohlcv_data: list[OHLCVRow] = Field(
        default_factory=list,
        min_length=0,
        max_length=500,
        description="OHLCV data (alternate key from Nivesh orchestrator)",
    )
    ticker: str = Field(default="UNKNOWN", max_length=32, description="Stock ticker for logging")
    model_type: str = Field(
        default="lightgbm",
        pattern="^lightgbm$",
        description="Kept for backward compatibility; only the LightGBM booster is served",
    )


class PredictionResult(BaseModel):
    """Prediction result for a single stock."""
    model_config = ConfigDict(protected_namespaces=())  # allow the model_validated field

    ticker: str = ""
    direction: int | None = Field(
        default=None,
        ge=-1,
        le=1,
        description="Alias for expected_direction used by backend clients",
    )
    expected_direction: int = Field(
        ...,
        ge=-1,
        le=1,
        description="-1 (bearish), 0 (neutral), 1 (bullish)",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Alias for confidence_score used by backend clients",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Calibrated confidence (0-1)",
    )
    ml_engine_mode: str = Field(
        default="fallback_technical_heuristic",
        description="Mode of ML Engine prediction",
    )
    lightgbm_loaded: bool = Field(
        default=False,
        description="Whether LightGBM model was loaded and used",
    )
    features: list[str] = Field(
        default_factory=list,
        description="Reserved; no feature attribution is computed (always empty)",
    )
    prediction_time_ms: float = Field(
        ...,
        description="Inference wall-clock time in milliseconds",
    )
    raw_score: float | None = Field(
        default=None,
        description="Raw model score before thresholding",
    )
    model_version: str | None = Field(
        default=None,
        description="Trained model version identifier",
    )
    horizon: int = Field(
        default=DEFAULT_PREDICTION_HORIZON,
        description="Prediction target horizon in trading days",
    )
    feature_count: int = Field(
        default=0,
        description="Total feature count expected by the active model",
    )
    fallback_used: bool = Field(
        default=True,
        description="Whether the response came from a fallback path",
    )
    signal_state: str = Field(
        default="no_edge",
        description="'ok' only when a validated model produced a direction; otherwise 'no_edge'",
    )
    p_up: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Booster probability of an up move over the horizon",
    )
    base_rate: float | None = Field(
        default=None,
        description="Training base rate of the up class",
    )
    model_validated: bool = Field(
        default=False,
        description="Whether the deployed model passed the promotion gate",
    )


class ModelStatus(BaseModel):
    """Model metadata response."""
    model_config = ConfigDict(protected_namespaces=())  # allow the model_validated field

    lightgbm_loaded: bool
    scaler_loaded: bool
    ml_engine_mode: str
    supported_horizons: list[int]
    feature_count: int
    lightgbm_path: str | None = None
    model_version: str | None = None
    model_validated: bool = False


# ── Version Detection ─────────────────────────────────────────────────────────


def _detect_model_version(model_path: Path) -> str | None:
    """Try to read model version from VERSION file next to model or training artifacts."""
    deployed_version_file = model_path.parent / "DEPLOYED_VERSION"
    if deployed_version_file.exists():
        try:
            return deployed_version_file.read_text().strip()
        except Exception:
            pass

    # Check for VERSION file next to the model
    version_file = model_path.parent / "VERSION"
    if version_file.exists():
        try:
            return version_file.read_text().strip()
        except Exception:
            pass

    # Check training/artifacts for version directories or metadata
    artifacts_dir = model_path.parent.parent / "training" / "artifacts"
    if artifacts_dir.exists():
        # Look for a version metadata JSON
        meta_file = artifacts_dir / "model_metadata.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
                return meta.get("version") or meta.get("model_version")
            except Exception:
                pass

        # Fall back to latest versioned subdirectory name
        try:
            version_dirs = sorted(
                [d.name for d in artifacts_dir.iterdir() if d.is_dir()],
                reverse=True,
            )
            if version_dirs:
                return version_dirs[0]
        except Exception:
            pass

    return None


def _load_manifest() -> dict[str, Any]:
    """Return the parsed model manifest, or {} when it is absent or unreadable.

    Without a manifest whose gate passed, the booster is served as no_edge.
    """
    try:
        manifest = json.loads(MANIFEST_PATH.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        _LOG.error("Ignoring unreadable model manifest %s: %s", MANIFEST_PATH, exc)
        return {}
    return manifest if isinstance(manifest, dict) else {}


# ── Lifespan ───────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Load models and scaler at startup; clean up at shutdown."""
    global _lightgbm_model, _feature_scaler
    global _feature_computer, _inference_engine, _model_version, _model_validated

    _LOG.info("ml-engine starting up — loading models...")

    # LightGBM
    try:
        _lightgbm_model = ModelLoader.load_lightgbm(LIGHTGBM_MODEL_PATH)
        _LOG.info("LightGBM model loaded from %s", LIGHTGBM_MODEL_PATH)

        # Detect model version from VERSION file or training artifacts
        _model_version = _detect_model_version(LIGHTGBM_MODEL_PATH)
        if _model_version:
            _LOG.info("Model version detected: %s", _model_version)
        else:
            _LOG.info("No model version file found — version will be None")
    except FileNotFoundError:
        _LOG.warning(
            "LightGBM model not found at %s — prediction will use fallback heuristic",
            LIGHTGBM_MODEL_PATH,
        )
        _lightgbm_model = None

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
    manifest = _load_manifest() if _lightgbm_model is not None else {}
    gate = manifest.get("gate")
    _model_validated = isinstance(gate, dict) and gate.get("passed") is True
    _inference_engine = InferenceEngine(
        lightgbm_model=_lightgbm_model,
        lgb_params=LIGHTGBM_PARAMS,
        confidence_config=CONFIDENCE_CONFIG,
        lgb_objective=_lightgbm_model.dump_model().get("objective") if _lightgbm_model is not None else None,
        model_validated=_model_validated,
        base_rate=manifest.get("base_rate"),
        neutral_band=manifest.get("neutral_band"),
    )
    if _lightgbm_model is not None and not _model_validated:
        _LOG.warning("No passed promotion gate in %s — predictions are served as no_edge", MANIFEST_PATH)

    if not os.getenv("ML_ENGINE_API_KEY"):
        _LOG.warning("ML_ENGINE_API_KEY is not set — prediction endpoints accept unauthenticated calls")
    _LOG.info("ml-engine ready — listening on port 8001")
    yield

    _LOG.info("ml-engine shutting down — releasing model resources")
    _lightgbm_model = None
    _feature_scaler = None


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Nivesh ML Engine",
    description=(
        "Standalone inference microservice — LightGBM model "
        "with Alpha158 features for Indian equity prediction"
    ),
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(research_router)


# ── Health ─────────────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": "ml-engine"}


# ── Model Status ───────────────────────────────────────────────────────────────


@app.get("/model/status", response_model=ModelStatus, dependencies=[Depends(require_api_key)])
async def model_status() -> ModelStatus:
    """Return loaded model metadata."""
    lightgbm_loaded = _lightgbm_model is not None
    return ModelStatus(
        lightgbm_loaded=lightgbm_loaded,
        scaler_loaded=_feature_scaler is not None,
        ml_engine_mode="trained_lightgbm_baseline" if lightgbm_loaded else "fallback_technical_heuristic",
        supported_horizons=SUPPORTED_HORIZONS,
        feature_count=len(FEATURE_LIST),
        lightgbm_path=str(LIGHTGBM_MODEL_PATH) if lightgbm_loaded else None,
        model_version=_model_version,
        model_validated=_model_validated,
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


def _is_stale(rows: list[OHLCVRow]) -> bool:
    """True when the last row carries an ISO date older than MAX_INPUT_AGE_DAYS."""
    if not rows or not rows[-1].date:
        return False
    try:
        last = date.fromisoformat(rows[-1].date[:10])
    except ValueError:
        return False
    return (datetime.now(timezone.utc).date() - last).days > MAX_INPUT_AGE_DAYS


# ── Predict ────────────────────────────────────────────────────────────────────


# Plain ``def``: FastAPI runs it in its threadpool, so CPU-bound polars/LightGBM
# work never blocks the event loop (and /health) for other requests.
@app.post("/predict/single", response_model=PredictionResult, dependencies=[Depends(require_api_key)])
def predict_single(req: SingleStockRequest) -> PredictionResult:
    """Predict for a single stock from its OHLCV history."""
    if _feature_computer is None or _inference_engine is None:
        raise HTTPException(status_code=503, detail="Model engine not initialized")

    t0 = time.perf_counter()

    rows = req.ohlcv_data or req.ohlcv
    if _is_stale(rows):
        raise HTTPException(status_code=422, detail="stale_input")

    df = _ohlcv_to_polars(rows)

    # Static details only: exception text stays in the server log.
    try:
        features_df = _feature_computer.compute_all(df)
    except InsufficientHistoryError:
        _LOG.warning("Insufficient history for %s (%d rows)", req.ticker, len(rows))
        raise HTTPException(status_code=422, detail="insufficient_history")
    except InvalidOHLCVError:
        _LOG.warning("Invalid OHLCV input for %s", req.ticker, exc_info=True)
        raise HTTPException(status_code=422, detail="invalid_ohlcv")
    except Exception:
        _LOG.exception("Feature computation failed for %s", req.ticker)
        raise HTTPException(status_code=422, detail="Feature computation failed")

    try:
        result = _inference_engine.predict(
            features_df,
            ticker=req.ticker,
            model_type=req.model_type,
        )
    except Exception:
        _LOG.exception("Inference failed for %s", req.ticker)
        raise HTTPException(status_code=500, detail="Inference failed")

    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    expected_direction = result["expected_direction"]
    confidence_score = result["confidence_score"]
    lightgbm_loaded = _lightgbm_model is not None
    return PredictionResult(
        ticker=req.ticker,
        direction=expected_direction,
        expected_direction=expected_direction,
        confidence=confidence_score,
        confidence_score=confidence_score,
        ml_engine_mode="trained_lightgbm_baseline" if lightgbm_loaded else "fallback_technical_heuristic",
        lightgbm_loaded=lightgbm_loaded,
        features=[],  # reserved: no feature attribution is computed
        prediction_time_ms=round(elapsed_ms, 2),
        raw_score=result.get("raw_score"),
        signal_state=result["signal_state"],
        p_up=result["p_up"],
        base_rate=result["base_rate"],
        model_validated=_model_validated,
        model_version=_model_version if lightgbm_loaded else None,
        horizon=DEFAULT_PREDICTION_HORIZON,
        feature_count=len(FEATURE_LIST),
        fallback_used=not lightgbm_loaded,
    )

