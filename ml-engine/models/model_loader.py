"""
ModelLoader — unified interface for loading and saving ML model artifacts.

Supports:
- LightGBM booster (text format: lgb_model.txt)
- TRA PyTorch model (state dict: tra_model.pt)
- Feature scaler (JSON: feature_scaler.json — median + IQR per feature)

Design: mirrors QlibEngine's singleton pattern (threading.Lock on __new__)
but keeps model loading explicit at startup via lifespan.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

_LOG = logging.getLogger(__name__)


class ModelLoader:
    """Static methods for loading model artifacts. Not a singleton — caller
    owns the loaded objects."""

    # ── LightGBM ───────────────────────────────────────────────────────────

    @staticmethod
    def load_lightgbm(path: Path) -> Any:
        """Load a trained LightGBM booster from a text file.

        Returns a lightgbm.Booster instance, or None if the file is missing
        and the caller should fall back to heuristic prediction.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"LightGBM model not found: {path}")

        import lightgbm as lgb

        model = lgb.Booster(model_file=str(path))
        _LOG.info("LightGBM model loaded: %s features", model.num_feature())
        return model

    @staticmethod
    def save_lightgbm(model: Any, path: Path) -> None:
        """Save a LightGBM booster to a text file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        model.save_model(str(path))
        _LOG.info("LightGBM model saved to %s", path)

    # ── TRA (PyTorch) ──────────────────────────────────────────────────────

    @staticmethod
    def load_tra(path: Path) -> Any:
        """Load a TRA PyTorch model from a .pt state dict file.

        Returns an nn.Module instance in eval mode, or None if the file
        is missing and the caller should fall back.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"TRA model not found: {path}")

        import torch

        from config import TRA_CONFIG

        # Lazy import to avoid circular dependency — TRA is defined in pipeline.inference
        from pipeline.tra_model import TRAModel

        model = TRAModel(
            input_dim=TRA_CONFIG["input_dim"],
            hidden_dim=TRA_CONFIG["hidden_dim"],
            num_layers=TRA_CONFIG["num_layers"],
            num_states=TRA_CONFIG["num_states"],
            seq_len=TRA_CONFIG["seq_len"],
            dropout=TRA_CONFIG["dropout"],
        )
        state = torch.load(str(path), map_location="cpu", weights_only=True)
        model.load_state_dict(state)
        model.eval()
        _LOG.info("TRA model loaded from %s", path)
        return model

    @staticmethod
    def save_tra(model: Any, path: Path) -> None:
        """Save a TRA PyTorch model state dict."""
        import torch

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), str(path))
        _LOG.info("TRA model saved to %s", path)

    # ── Scaler ─────────────────────────────────────────────────────────────

    @staticmethod
    def load_scaler(path: Path) -> dict[str, dict[str, float]]:
        """Load RobustZScoreNorm parameters from JSON.

        Expected shape: {"feature_name": {"median": float, "iqr": float}, ...}
        Returns empty dict if file missing.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Scaler not found: {path}")

        with open(path, "r") as f:
            scaler = json.load(f)
        _LOG.info("Scaler loaded with %d features", len(scaler))
        return scaler

    @staticmethod
    def save_scaler(scaler: dict[str, dict[str, float]], path: Path) -> None:
        """Save RobustZScoreNorm parameters to JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(scaler, f, indent=2)
        _LOG.info("Scaler saved with %d features", len(scaler))


# ── Convenience ────────────────────────────────────────────────────────────────


def load_model(model_type: str, path: Path) -> Any:
    """Dispatch to the correct loader based on model type string.

    Args:
        model_type: "lightgbm", "tra", or "scaler"
        path: Path to the model file

    Returns:
        Loaded model object or scaler dict.
    """
    loaders = {
        "lightgbm": ModelLoader.load_lightgbm,
        "tra": ModelLoader.load_tra,
        "scaler": ModelLoader.load_scaler,
    }
    if model_type not in loaders:
        raise ValueError(
            f"Unknown model type '{model_type}'. Choose from: {list(loaders)}"
        )
    return loaders[model_type](path)
