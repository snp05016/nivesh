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
    deploy_to_production(artifact["model_version"])  # gated: raises GateFailedError

Artifacts are immutable: saving a version that already exists raises
FileExistsError. Production is models/lgb_model.txt plus models/MANIFEST.json,
which ml-engine verifies at startup.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
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
_PRODUCTION_MANIFEST_PATH = _ML_ENGINE_DIR / "models" / "MANIFEST.json"

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
    # ..._YYYYMMDD or ..._YYYYMMDD_<gitsha7>
    match = re.search(r"_(\d{8})(?:_[0-9a-z]+)?$", version)
    return match.group(1) if match else "00000000"


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
        Training parameters, data range, n_samples, etc. ``data_sha256``
        (hash of the feature frame) is carried into the production manifest.
    validation_metrics : list[dict]
        Per-fold walk-forward validation results.
    calibration_report : dict
        Overall calibration statistics.
    model_version : str or None
        Explicit version string. If None, auto-generated from today's date.
        An existing version raises FileExistsError (artifacts are immutable).
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
    artifact_dir.mkdir()  # FileExistsError: an artifact is never overwritten

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


class GateFailedError(RuntimeError):
    """The candidate failed the promotion gate; nothing was deployed."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def deploy_to_production(model_version: str, status: str = "candidate") -> Path:
    """Gate, verify and atomically deploy a registry artifact.

    Runs the promotion gate first and raises GateFailedError before anything
    is copied (there is no override). Then checks the booster's feature count
    against the artifact's features.json and writes models/lgb_model.txt and
    models/MANIFEST.json (sha256, objective, trees, features, git SHA, data
    sha256, gate result, base rate, neutral band) via temp files + os.replace.

    Raises
    ------
    FileNotFoundError
        If the specified version does not exist in the registry.
    GateFailedError
        If the promotion gate fails.
    ValueError
        If the booster's feature count differs from features.json.
    """
    artifact_dir = REGISTRY_DIR / status / model_version
    source_model = artifact_dir / "model.txt"
    if not source_model.exists():
        raise FileNotFoundError(
            f"model.txt for '{model_version}' not found in {REGISTRY_DIR}/{status}"
        )

    gate = evaluate_deployment_guardrails(model_version, status=status)
    if not gate["passed"]:
        raise GateFailedError(
            f"{model_version} failed the promotion gate: {gate['reasons_for_rejection']}"
        )

    import lightgbm as lgb

    from training.provenance import git_sha

    booster = lgb.Booster(model_file=str(source_model))
    features = _read_json(artifact_dir / "features.json")
    if booster.num_feature() != len(features):
        raise ValueError(
            f"booster has {booster.num_feature()} features, features.json lists {len(features)}"
        )
    metadata_path = artifact_dir / "metadata.json"
    metadata = _read_json(metadata_path) if metadata_path.exists() else {}

    manifest = {
        "model_version": model_version,
        "sha256": _sha256(source_model),
        "objective": booster.dump_model()["objective"],
        "num_trees": booster.num_trees(),
        "num_features": booster.num_feature(),
        "feature_list": features,
        "git_sha": git_sha() or "unknown",
        "data_sha256": metadata.get("data_sha256"),
        "gate": gate,
        "base_rate": gate.get("base_rate"),
        "neutral_band": gate.get("neutral_band"),
        "deployed_at": datetime.now(timezone.utc).isoformat(),
    }

    _PRODUCTION_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_model = _PRODUCTION_MODEL_PATH.with_name(_PRODUCTION_MODEL_PATH.name + ".tmp")
    tmp_manifest = _PRODUCTION_MANIFEST_PATH.with_name(_PRODUCTION_MANIFEST_PATH.name + ".tmp")
    shutil.copyfile(source_model, tmp_model)
    _write_json(tmp_manifest, manifest)
    # Model first: a crash in between leaves a sha mismatch, which ml-engine refuses to serve.
    os.replace(tmp_model, _PRODUCTION_MODEL_PATH)
    os.replace(tmp_manifest, _PRODUCTION_MANIFEST_PATH)

    _LOG.info("Production deployment complete: %s -> %s", model_version, _PRODUCTION_MODEL_PATH)
    return _PRODUCTION_MODEL_PATH


def evaluate_deployment_guardrails(model_version: str, status: str = "candidate") -> dict:
    """Run the promotion gate (training.promotion_gate) on the artifact's
    oof_predictions.csv and write the result to gate_result.json.

    Returns the gate result plus 'reasons_for_rejection' (same list as 'reasons').
    """
    artifact_dir = REGISTRY_DIR / status / model_version
    if not artifact_dir.exists():
        raise FileNotFoundError(f"Model version '{model_version}' not found in {REGISTRY_DIR}/{status}")

    oof_path = artifact_dir / "oof_predictions.csv"
    if not oof_path.exists():
        result: dict[str, Any] = {
            "passed": False, "checks": {}, "reasons": ["no out-of-fold predictions"],
            "base_rate": None, "neutral_band": None,
        }
    else:
        import pandas as pd

        from training.promotion_gate import evaluate_gate

        result = evaluate_gate(pd.read_csv(oof_path))
    result["reasons_for_rejection"] = result["reasons"]
    _write_json(artifact_dir / "gate_result.json", result)
    return result
