"""
Model Registry — versioned storage for trained LightGBM model artifacts.

Saves and loads model artifacts with metadata, feature lists, validation
metrics, and calibration reports. Each trained model gets a versioned
directory under REGISTRY_DIR with all artifacts needed to reproduce or
deploy the model.

Usage
-----
    from training.model_registry import save_model_artifact, load_model_artifact

    path = save_model_artifact(model, features, metadata, metrics, calibration)
    artifact = load_model_artifact()  # loads latest
    deploy_to_production(artifact["model_version"])
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOG = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_ML_ENGINE_DIR = Path(__file__).resolve().parent.parent
REGISTRY_DIR = _ML_ENGINE_DIR / "models" / "registry"

# Production model path (mirrors config.py:LIGHTGBM_MODEL_PATH)
_PRODUCTION_MODEL_PATH = _ML_ENGINE_DIR / "models" / "lgb_model.txt"
_PRODUCTION_FEATURES_PATH = _ML_ENGINE_DIR / "models" / "features.json"
_PRODUCTION_VERSION_PATH = _ML_ENGINE_DIR / "models" / "DEPLOYED_VERSION"

# Version format prefix
_VERSION_PREFIX = "lightgbm_baseline_alpha158_v1"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _generate_model_version() -> str:
    """Generate a model version string with today's date.

    Format: lightgbm_baseline_alpha158_v1_YYYYMMDD
    """
    datestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{_VERSION_PREFIX}_{datestamp}"


def _parse_version_date(version: str) -> str:
    """Extract the YYYYMMDD suffix from a version string for sorting."""
    # Version format: lightgbm_baseline_alpha158_v1_YYYYMMDD
    parts = version.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 8:
        return parts[1]
    return "00000000"


def _write_json(path: Path, data: Any) -> None:
    """Write data to a JSON file with consistent formatting."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _read_json(path: Path) -> Any:
    """Read and parse a JSON file."""
    with open(path, "r") as f:
        return json.load(f)


# ── Public API ────────────────────────────────────────────────────────────────


def save_model_artifact(
    model: Any,
    feature_list: list[str],
    training_metadata: dict,
    validation_metrics: list[dict],
    calibration_report: dict,
    model_version: str | None = None,
    status: str = "candidate",
    calibrator: Any | None = None,
    oof_predictions: Any | None = None,
) -> Path:
    """Save a trained LightGBM model and all associated artifacts.

    Parameters
    ----------
    model : lightgbm.Booster or LGBEnsembleModel
        The trained model. If LGBEnsembleModel, the internal Booster is
        extracted via ``model._model``.
    feature_list : list[str]
        Ordered list of feature names used during training.
    training_metadata : dict
        Training parameters, data range, n_samples, etc.
    validation_metrics : list[dict]
        Per-fold walk-forward validation results.
    calibration_report : dict
        Overall calibration statistics.
    model_version : str or None
        Explicit version string. If None, auto-generated from today's date.
    status : str
        Model status: 'candidate', 'stable', 'deprecated', 'latest'. Default is 'candidate'.
    calibrator : Any or None
        Fitted calibration object (e.g. IsotonicRegression or LogisticRegression) to save via joblib.
    oof_predictions : pandas.DataFrame or None
        Out-of-fold (and holdout) predictions, written to oof_predictions.csv
        as the input of the promotion gate.

    Returns
    -------
    Path
        Directory containing all saved artifacts.
    """
    if model_version is None:
        model_version = _generate_model_version()
        
    status_dir = REGISTRY_DIR / status
    status_dir.mkdir(parents=True, exist_ok=True)

    artifact_dir = status_dir / model_version
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # ── Save the LightGBM model ──────────────────────────────────────────
    model_path = artifact_dir / "model.txt"

    # Handle both raw Booster and LGBEnsembleModel wrapper
    try:
        import lightgbm as lgb
    except ImportError:
        raise ImportError(
            "lightgbm is required to save model artifacts. "
            "Install with: pip install lightgbm"
        )

    if isinstance(model, lgb.Booster):
        booster = model
    elif hasattr(model, "_model") and isinstance(model._model, lgb.Booster):
        booster = model._model
    else:
        raise TypeError(
            f"Expected lightgbm.Booster or LGBEnsembleModel, got {type(model).__name__}"
        )

    booster.save_model(str(model_path))
    _LOG.info("Model saved to %s", model_path)

    # ── Save feature list ────────────────────────────────────────────────
    _write_json(artifact_dir / "features.json", feature_list)

    # ── Save training metadata with timestamp ────────────────────────────
    metadata = {
        **training_metadata,
        "model_version": model_version,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "num_features": len(feature_list),
        "num_trees": booster.num_trees(),
    }
    _write_json(artifact_dir / "metadata.json", metadata)

    # ── Save validation metrics ──────────────────────────────────────────
    _write_json(artifact_dir / "validation_metrics.json", validation_metrics)

    # ── Save calibration report ──────────────────────────────────────────
    _write_json(artifact_dir / "calibration_report.json", calibration_report)

    # ── Save calibrator object ───────────────────────────────────────────
    if calibrator is not None:
        try:
            import joblib
            joblib.dump(calibrator, artifact_dir / "calibrator.joblib")
        except ImportError:
            _LOG.warning("joblib not installed; could not save calibrator object.")

    if oof_predictions is not None:
        oof_predictions.to_csv(artifact_dir / "oof_predictions.csv", index=False)

    # ── Save VERSION file ────────────────────────────────────────────────
    (artifact_dir / "VERSION").write_text(model_version, encoding="utf-8")

    _LOG.info(
        "Model artifact saved: version=%s, dir=%s, features=%d, trees=%d",
        model_version,
        artifact_dir,
        len(feature_list),
        booster.num_trees(),
    )

    return artifact_dir


def load_model_artifact(model_version: str | None = None, status: str = "stable") -> dict:
    """Load a model artifact from the registry.

    Parameters
    ----------
    model_version : str or None
        Specific version to load. If None, loads the latest version
        from the 'stable' directory (or 'candidate' if no stable exists).
    status : str
        Specific status directory to load from if model_version is provided. Default is 'stable'.

    Returns
    -------
    dict
        {"model": Booster, "features": [...], "metadata": {...},
         "model_version": "..."}

    Raises
    ------
    FileNotFoundError
        If no artifacts exist or the specified version is not found.
    """
    if model_version is None:
        versions = list_model_versions(status="stable")
        if not versions:
            versions = list_model_versions(status="candidate")
        if not versions:
            raise FileNotFoundError(
                f"No stable or candidate model artifacts found in {REGISTRY_DIR}"
            )
        model_version = versions[-1]  # latest by date sort
        status = "stable" if list_model_versions(status="stable") else "candidate"

    artifact_dir = REGISTRY_DIR / status / model_version
    if not artifact_dir.exists():
        raise FileNotFoundError(
            f"Model version '{model_version}' not found in {REGISTRY_DIR}/{status}"
        )

    model_path = artifact_dir / "model.txt"
    if not model_path.exists():
        raise FileNotFoundError(
            f"model.txt not found in artifact directory: {artifact_dir}"
        )

    # Lazy import lightgbm
    try:
        import lightgbm as lgb
    except ImportError:
        raise ImportError(
            "lightgbm is required to load model artifacts. "
            "Install with: pip install lightgbm"
        )

    booster = lgb.Booster(model_file=str(model_path))
    features = _read_json(artifact_dir / "features.json")
    metadata = _read_json(artifact_dir / "metadata.json")
    
    calibrator = None
    calibrator_path = artifact_dir / "calibrator.joblib"
    if calibrator_path.exists():
        try:
            import joblib
            calibrator = joblib.load(calibrator_path)
        except ImportError:
            _LOG.warning("joblib not installed; could not load calibrator object.")

    _LOG.info(
        "Model artifact loaded: version=%s, features=%d, trees=%d",
        model_version,
        len(features),
        booster.num_trees(),
    )

    return {
        "model": booster,
        "features": features,
        "metadata": metadata,
        "model_version": model_version,
        "calibrator": calibrator,
    }


def list_model_versions(status: str = "stable") -> list[str]:
    """Return sorted list of available model versions for a given status.

    Sorted by the YYYYMMDD date suffix (ascending), so the last element
    is the most recent version.

    Parameters
    ----------
    status : str
        The registry status folder to query (e.g. 'stable', 'candidate').

    Returns
    -------
    list[str]
        Version strings, e.g. ["lightgbm_baseline_alpha158_v1_20260620", ...]
    """
    status_dir = REGISTRY_DIR / status
    if not status_dir.exists():
        return []

    versions = [
        d.name
        for d in status_dir.iterdir()
        if d.is_dir() and (d / "model.txt").exists()
    ]

    versions.sort(key=_parse_version_date)
    return versions


def get_latest_model_path() -> Path | None:
    """Return the path to the latest model.txt in the registry.

    This is what the production endpoint uses to check whether a trained
    model exists before falling back to heuristic prediction.

    Returns
    -------
    Path or None
        Path to model.txt, or None if no models have been trained.
    """
    versions = list_model_versions(status="stable")
    if versions:
        return REGISTRY_DIR / "stable" / versions[-1] / "model.txt"
        
    versions = list_model_versions(status="candidate")
    if versions:
        return REGISTRY_DIR / "candidate" / versions[-1] / "model.txt"
        
    return None


def deploy_to_production(model_version: str, status: str = "stable") -> Path:
    """Deploy a model artifact to the production model path.

    Copies model.txt to LIGHTGBM_MODEL_PATH (ml-engine/models/lgb_model.txt),
    copies features.json alongside it, and writes a DEPLOYED_VERSION file
    recording which registry version is currently active.

    Parameters
    ----------
    model_version : str
        The registry version to deploy.
    status : str
        The status directory where the version resides.

    Returns
    -------
    Path
        The production model path (ml-engine/models/lgb_model.txt).

    Raises
    ------
    FileNotFoundError
        If the specified version does not exist in the registry.
    """
    artifact_dir = REGISTRY_DIR / status / model_version
    if not artifact_dir.exists():
        raise FileNotFoundError(
            f"Model version '{model_version}' not found in {REGISTRY_DIR}/{status}"
        )

    source_model = artifact_dir / "model.txt"
    source_features = artifact_dir / "features.json"

    if not source_model.exists():
        raise FileNotFoundError(
            f"model.txt not found in artifact directory: {artifact_dir}"
        )

    # Ensure production directory exists
    _PRODUCTION_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Copy model file
    shutil.copy2(str(source_model), str(_PRODUCTION_MODEL_PATH))
    _LOG.info("Model deployed to %s", _PRODUCTION_MODEL_PATH)

    # Copy features file
    if source_features.exists():
        shutil.copy2(str(source_features), str(_PRODUCTION_FEATURES_PATH))
        _LOG.info("Features deployed to %s", _PRODUCTION_FEATURES_PATH)

    # Write deployed version marker
    _PRODUCTION_VERSION_PATH.write_text(model_version, encoding="utf-8")
    _LOG.info("Deployed version marker: %s", _PRODUCTION_VERSION_PATH)

    _LOG.info(
        "Production deployment complete: %s -> %s",
        model_version,
        _PRODUCTION_MODEL_PATH,
    )

    return _PRODUCTION_MODEL_PATH

def evaluate_deployment_guardrails(model_version: str, status: str = "candidate") -> dict:
    """Evaluate if a candidate model meets criteria for promotion to stable.
    
    Returns a dict with 'passed' bool and 'reasons_for_rejection' list.
    """
    artifact_dir = REGISTRY_DIR / status / model_version
    if not artifact_dir.exists():
        raise FileNotFoundError(f"Model version '{model_version}' not found in {REGISTRY_DIR}/{status}")
        
    validation_metrics_path = artifact_dir / "validation_metrics.json"
    calibration_report_path = artifact_dir / "calibration_report.json"
    
    if not validation_metrics_path.exists() or not calibration_report_path.exists():
        return {
            "passed": False,
            "mean_hit_rate": 0.0,
            "brier_score": 1.0,
            "reasons_for_rejection": ["Missing validation_metrics.json or calibration_report.json"]
        }
        
    validation_metrics = _read_json(validation_metrics_path)
    calibration_report = _read_json(calibration_report_path)
    
    # Calculate aggregate hit rate across folds
    hit_rates = [f["hit_rate"] for f in validation_metrics if "hit_rate" in f]
    mean_hit_rate = sum(hit_rates) / len(hit_rates) if hit_rates else 0.0
    
    brier_score = calibration_report.get("brier_score", 1.0)
    
    passed = True
    reasons = []
    
    # Hardcoded threshold: hit rate > 53%
    if mean_hit_rate <= 0.53:
        passed = False
        reasons.append(f"Hit rate {mean_hit_rate:.4f} <= 0.5300")
        
    # Hardcoded threshold: Brier score < 0.2529 (All_Features baseline)
    if brier_score >= 0.2529:
        passed = False
        reasons.append(f"Brier score {brier_score:.4f} >= 0.2529")
        
    return {
        "passed": passed,
        "mean_hit_rate": mean_hit_rate,
        "brier_score": brier_score,
        "reasons_for_rejection": reasons
    }

