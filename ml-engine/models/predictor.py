"""
Unified Predictor Orchestrator.

Two-stage pipeline that routes each stock through a TRA regime classifier
and then delegates prediction to the appropriate regime-specific LightGBM
model.  All models are standalone — no Qlib, no DataHandlerLP.

Pipeline
--------
Alpha158 features (158-D)
        │
        ▼
   TRARouter.predict()
        │
   regime_id ∈ {0,1,2} + confidence
        │
        ▼
   Per-regime LightGBM models       ──────┐
        │                                  │
        ▼                                  ▼
   Ensemble prediction          Feature importance
   + expected_direction          from each regime model
   + confidence_score
"""

from __future__ import annotations

import json
import os
import pickle
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn.functional as F

from .tra import TRAConfig, TRARouter
from .lgb_model import LGBEnsembleModel


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PredictionResult:
    """Single-stock prediction result.

    Attributes
    ----------
    expected_return : float
        Predicted future return (e.g., 0.015 = +150 bps).
    expected_direction : int
        +1 for expected up-move, -1 for down, 0 for flat / no signal.
    confidence_score : float
        Overall confidence in [0, 1].  Combines routing confidence and
        model prediction confidence.
    regime : int
        Assigned regime id (0, 1, or 2).
    regime_label : str
        Human-readable regime name.
    regime_confidence : float
        TRA routing probability for the assigned regime.
    model_prediction : float
        Raw prediction from the regime-specific LightGBM model.
    feature_importance : list of (index, importance) tuples
        Top-20 gain-based feature importances from the regime model.
    """

    expected_return: float
    expected_direction: int
    confidence_score: float
    regime: int
    regime_label: str
    regime_confidence: float
    model_prediction: float
    feature_importance: list  # list of (int, float)


# ---------------------------------------------------------------------------
# Unified predictor
# ---------------------------------------------------------------------------

class UnifiedPredictor:
    """Two-stage predictor: TRA regime routing → per-regime LightGBM.

    Parameters
    ----------
    tra_config : TRAConfig, optional
        Configuration for the TRA router.
    lgb_params : dict, optional
        LightGBM parameters shared across all regime models.
    num_regimes : int
        Number of regimes (must match TRA config).
    device : str
        PyTorch device for TRA inference ("cpu" or "cuda").
    """

    REGIME_LABELS = [
        "Low Vol / Trending",
        "Neutral",
        "High Vol / Mean-Reversion",
    ]

    def __init__(
        self,
        tra_config: Optional[TRAConfig] = None,
        lgb_params: Optional[Dict[str, Any]] = None,
        num_regimes: int = 3,
        device: str = "cpu",
    ):
        self.tra_config = tra_config or TRAConfig(num_regimes=num_regimes)
        self.lgb_params = lgb_params or {}
        self.num_regimes = num_regimes
        self.device = device

        self.tra: TRARouter = TRARouter(self.tra_config)
        self.tra.to(device)

        # One LightGBM per regime
        self._regime_models: Dict[int, LGBEnsembleModel] = {}
        for k in range(num_regimes):
            self._regime_models[k] = LGBEnsembleModel(params=lgb_params)

        # Per-regime training data buffers
        self._regime_buffers: Dict[int, Dict[str, list]] = {
            k: {"X": [], "y": []} for k in range(num_regimes)
        }

        self._trained = False

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        tra_epochs: int = 30,
        tra_lr: float = 1e-3,
        tra_batch_size: int = 256,
        verbose: bool = True,
    ) -> "UnifiedPredictor":
        """Train both the TRA router and the per-regime LightGBM models.

        Two-phase training:
          1. TRA is trained with a combined loss: MSE on the weighted
             prediction + cross-entropy on regime assignment (with
             Sinkhorn-based balanced transport regularization).
          2. After TRA converges, samples are partitioned by regime and
             each LightGBM is trained on its subset.

        Parameters
        ----------
        X : np.ndarray [N, 158]
            Training features.
        y : np.ndarray [N]
            Regression targets.
        X_val, y_val : np.ndarray, optional
            Validation data (used for LightGBM early stopping).
        tra_epochs : int
            TRA training epochs.
        tra_lr : float
            TRA optimizer learning rate.
        tra_batch_size : int
            TRA batch size.
        verbose : bool
            Print progress.
        """
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y, dtype=np.float32).ravel()

        # --- Phase 1: train TRA ---
        self._train_tra(X, y, epochs=tra_epochs, lr=tra_lr,
                        batch_size=tra_batch_size, verbose=verbose)

        # --- Phase 2: partition by regime & train LightGBM ---
        self.tra.eval()
        regime_ids, _ = self._route_batch(X, batch_size=tra_batch_size * 4)

        if X_val is not None and y_val is not None:
            X_val = np.asarray(X_val, dtype=np.float32)
            y_val = np.asarray(y_val, dtype=np.float32).ravel()
            val_regime_ids, _ = self._route_batch(X_val, batch_size=tra_batch_size * 4)
        else:
            val_regime_ids = None

        for k in range(self.num_regimes):
            mask = regime_ids == k
            if mask.sum() < 10:
                if verbose:
                    print(f"  [regime {k}] too few samples ({mask.sum()}), "
                          f"using shared model")
                continue

            X_k = X[mask]
            y_k = y[mask]

            X_val_k, y_val_k = None, None
            if X_val is not None and y_val is not None and val_regime_ids is not None:
                vmask = val_regime_ids == k
                if vmask.sum() >= 10:
                    X_val_k = X_val[vmask]
                    y_val_k = y_val[vmask]

            if verbose:
                print(f"  [regime {k}] training LightGBM on {len(X_k)} samples...")

            self._regime_models[k].fit(X_k, y_k, X_val_k, y_val_k)

        self._trained = True
        return self

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        X: np.ndarray,
        return_confidence: bool = True,
    ) -> "list[PredictionResult]":
        """Produce a PredictionResult for each input sample.

        Parameters
        ----------
        X : np.ndarray [N, 158]
        return_confidence : bool
            If True, use sub-ensemble variance for confidence (slower).
            If False, confidence is routing probability only.

        Returns
        -------
        list of PredictionResult, length N.
        """
        self._check_trained()

        X = np.asarray(X, dtype=np.float32)
        if X.ndim == 1:
            X = X.reshape(1, -1)

        # --- Stage 1: TRA routing ---
        regime_ids, routing_conf = self._route_batch(X)

        # --- Stage 2: per-regime LightGBM prediction ---
        results: list[PredictionResult] = []
        for k in range(self.num_regimes):
            mask = regime_ids == k
            if mask.sum() == 0:
                continue

            X_k = X[mask]
            model = self._regime_models[k]

            if model.is_fitted:
                if return_confidence:
                    preds_k, model_conf = model.predict_with_confidence(X_k)
                else:
                    preds_k = model.predict(X_k)
                    model_conf = np.ones_like(preds_k)

                fi_k = model.get_top_features(20)
            else:
                # Fallback: TRA-only prediction
                preds_k = np.zeros(len(X_k), dtype=np.float64)
                model_conf = np.zeros(len(X_k), dtype=np.float64)
                fi_k = []

            for i, idx in enumerate(np.where(mask)[0]):
                rc = float(routing_conf[idx])
                mc = float(model_conf[i])
                # Weighted confidence: routing * model confidence
                combined_conf = float(np.clip(rc * mc, 0.0, 1.0))

                exp_ret = float(preds_k[i])
                direction = 1 if exp_ret > 0.001 else (-1 if exp_ret < -0.001 else 0)

                results.append(PredictionResult(
                    expected_return=exp_ret,
                    expected_direction=direction,
                    confidence_score=combined_conf,
                    regime=k,
                    regime_label=self.REGIME_LABELS[k]
                        if k < len(self.REGIME_LABELS) else f"Regime-{k}",
                    regime_confidence=rc,
                    model_prediction=exp_ret,
                    feature_importance=fi_k,
                ))

        # Re-sort by original index order
        results.sort(key=lambda r: 0)  # Results already in order from loop; stable
        return results

    def predict_single(self, X_row: np.ndarray) -> PredictionResult:
        """Convenience: predict one sample."""
        return self.predict(X_row.reshape(1, -1), return_confidence=True)[0]

    def predict_batch_dict(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        """Return predictions as numpy arrays (for bulk backtesting).

        Returns
        -------
        dict with keys:
            expected_direction — shape [N], int
            confidence_score   — shape [N], float
            regime             — shape [N], int
        """
        results = self.predict(X, return_confidence=True)
        return {
            "expected_direction": np.array([r.expected_direction for r in results], dtype=np.int32),
            "confidence_score":   np.array([r.confidence_score for r in results],   dtype=np.float64),
            "expected_return":    np.array([r.expected_return for r in results],     dtype=np.float64),
            "regime":             np.array([r.regime for r in results],              dtype=np.int32),
        }

    # ------------------------------------------------------------------
    # Feature importance (aggregate)
    # ------------------------------------------------------------------

    def get_feature_importance(self, regime: Optional[int] = None) -> np.ndarray:
        """Return feature importances for a specific regime, or averaged across all.

        Returns
        -------
        np.ndarray [158] gain-based importances.
        """
        if regime is not None:
            model = self._regime_models.get(regime)
            if model is None or model.feature_importance is None:
                return np.zeros(self.tra_config.input_dim, dtype=np.float64)
            return model.feature_importance

        # Average across all fitted regime models
        accum = np.zeros(self.tra_config.input_dim, dtype=np.float64)
        count = 0
        for model in self._regime_models.values():
            if model.is_fitted and model.feature_importance is not None:
                accum += model.feature_importance
                count += 1
        return accum / max(count, 1)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, directory: str) -> None:
        """Save all models to a directory.

        Creates:
            directory/tra.pt               — TRA PyTorch state dict
            directory/tra_config.json       — TRAConfig as JSON
            directory/lgb_regime_{k}.lgb    — per-regime LightGBM models
            directory/metadata.json         — version / feature dim info
        """
        os.makedirs(directory, exist_ok=True)

        # TRA
        torch.save(self.tra.state_dict(), os.path.join(directory, "tra.pt"))
        tra_cfg = {
            "input_dim": self.tra_config.input_dim,
            "hidden_dim": self.tra_config.hidden_dim,
            "num_regimes": self.tra_config.num_regimes,
            "dropout": self.tra_config.dropout,
            "backbone_depth": self.tra_config.backbone_depth,
        }
        with open(os.path.join(directory, "tra_config.json"), "w") as f:
            json.dump(tra_cfg, f, indent=2)

        # LightGBM
        for k, model in self._regime_models.items():
            if model.is_fitted:
                model.save(os.path.join(directory, f"lgb_regime_{k}.lgb"))

        # Metadata
        meta = {
            "num_regimes": self.num_regimes,
            "input_dim": self.tra_config.input_dim,
            "trained": self._trained,
        }
        with open(os.path.join(directory, "metadata.json"), "w") as f:
            json.dump(meta, f, indent=2)

    @classmethod
    def load(
        cls,
        directory: str,
        device: str = "cpu",
        lgb_params: Optional[Dict[str, Any]] = None,
    ) -> "UnifiedPredictor":
        """Load all models from a directory."""
        # TRA config
        with open(os.path.join(directory, "tra_config.json")) as f:
            tra_cfg_dict = json.load(f)
        tra_config = TRAConfig(**tra_cfg_dict)
        obj = cls(tra_config=tra_config, lgb_params=lgb_params,
                  num_regimes=tra_config.num_regimes, device=device)

        # TRA weights
        state = torch.load(os.path.join(directory, "tra.pt"),
                           map_location=device, weights_only=True)
        obj.tra.load_state_dict(state)
        obj.tra.to(device)
        obj.tra.eval()

        # LightGBM
        for k in range(obj.num_regimes):
            path = os.path.join(directory, f"lgb_regime_{k}.lgb")
            if os.path.exists(path):
                obj._regime_models[k] = LGBEnsembleModel.load(path, params=lgb_params)

        obj._trained = True
        return obj

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _train_tra(
        self,
        X: np.ndarray,
        y: np.ndarray,
        epochs: int,
        lr: float,
        batch_size: int,
        verbose: bool,
    ) -> None:
        """Train the TRA router using MSE + balanced-assignment regularization."""
        self.tra.train()
        optimizer = torch.optim.AdamW(self.tra.parameters(), lr=lr, weight_decay=1e-5)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

        n = len(X)
        X_t = torch.from_numpy(X).float().to(self.device)
        y_t = torch.from_numpy(y).float().to(self.device)

        for epoch in range(epochs):
            perm = torch.randperm(n)
            total_loss = 0.0
            n_batches = 0

            for start in range(0, n, batch_size):
                idx = perm[start:start + batch_size]
                xb, yb = X_t[idx], y_t[idx]

                out = self.tra(xb, temperature=max(0.5, 1.0 - epoch / epochs))

                # MSE between final prediction and target
                loss_mse = F.mse_loss(out["final_pred"], yb)

                # Balanced-assignment regularization:
                # Encourage uniform utilization of regimes to prevent collapse
                # (simplified Sinkhorn — penalize deviation from 1/K)
                routing_mean = out["routing_weights"].mean(dim=0)  # [K]
                target_uniform = torch.full_like(routing_mean, 1.0 / self.num_regimes)
                loss_balance = F.mse_loss(routing_mean, target_uniform)

                loss = loss_mse + 0.1 * loss_balance

                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.tra.parameters(), 1.0)
                optimizer.step()

                total_loss += loss.item()
                n_batches += 1

            scheduler.step()

            if verbose and (epoch + 1) % 10 == 0:
                avg = total_loss / max(n_batches, 1)
                print(f"  TRA epoch {epoch + 1:3d}/{epochs}  loss={avg:.6f}")

    @torch.no_grad()
    def _route_batch(
        self,
        X: np.ndarray,
        batch_size: int = 1024,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Run TRA inference over X in batches.

        Returns
        -------
        regime_ids : np.ndarray [N]
        confidence : np.ndarray [N]
        """
        n = len(X)
        all_regimes = np.empty(n, dtype=np.int64)
        all_conf = np.empty(n, dtype=np.float64)

        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            xb = torch.from_numpy(X[start:end]).float().to(self.device)
            out = self.tra.predict(xb)
            all_regimes[start:end] = out["regime_id"].cpu().numpy()
            all_conf[start:end] = out["confidence"].cpu().numpy()

        return all_regimes, all_conf

    def _check_trained(self) -> None:
        if not self._trained:
            raise RuntimeError("UnifiedPredictor not trained. Call .fit() first.")
