"""
Temporal Routing Adaptor (TRA) — Lightweight regime classifier.

Routes stocks to specialized sub-models based on learned trading patterns.
Based on "Learning Multiple Stock Trading Patterns with Temporal Routing
Adaptor and Optimal Transport" (Lin et al., KDD 2021), simplified for
standalone use without Qlib.

Architecture
------------
Input:  Alpha158 feature vector → [batch, 158]
        ↓
        Shared backbone: 3-layer MLP with BatchNorm + Dropout → [batch, hidden_dim]
        ↓
        ┌──────────────┬──────────────────┐
        ↓              ↓                  ↓
   Regime Head    Predictor 0       Predictor 1    Predictor 2
   (classifier)   (regression)      (regression)   (regression)
        ↓              ↓                  ↓              ↓
   regime_id     pred_momentum     pred_neutral     pred_reversal
   + confidence
        ↓
        Final output: softmax-weighted blend of K predictor outputs

Regimes
-------
0 — "Low Vol / Trending"    — momentum-following stocks
1 — "Neutral"               — range-bound, no strong signal
2 — "High Vol / Mean-Reversion" — volatile, reversal candidates
"""

from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class TRAConfig:
    """Hyperparameters for the Temporal Routing Adaptor.

    Attributes
    ----------
    input_dim : int
        Dimensionality of input features (Alpha158 = 158).
    hidden_dim : int
        Hidden dimension of the shared backbone MLP.
    num_regimes : int
        Number of regime / predictor heads (K in the paper).
    dropout : float
        Dropout probability applied after each hidden layer.
    temperature : float
        Gumbel-Softmax temperature. Lower = harder assignments.
        Decays during training for progressively crisper routing.
    backbone_depth : int
        Number of hidden layers in the shared backbone (default 3).
    """

    def __init__(
        self,
        input_dim: int = 158,
        hidden_dim: int = 128,
        num_regimes: int = 3,
        dropout: float = 0.3,
        temperature: float = 1.0,
        backbone_depth: int = 3,
    ):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_regimes = num_regimes
        self.dropout = dropout
        self.temperature = temperature
        self.backbone_depth = backbone_depth


# ---------------------------------------------------------------------------
# Shared backbone
# ---------------------------------------------------------------------------

class _Backbone(nn.Module):
    """3-layer MLP backbone with BatchNorm and Dropout.

    Maps raw Alpha158 features → compact latent representation.
    """

    def __init__(self, config: TRAConfig):
        super().__init__()
        dims = [config.input_dim] + [config.hidden_dim] * config.backbone_depth
        layers: list[nn.Module] = []
        for i in range(len(dims) - 1):
            layers.append(nn.Linear(dims[i], dims[i + 1], bias=False))
            layers.append(nn.BatchNorm1d(dims[i + 1]))
            layers.append(nn.GELU())
            layers.append(nn.Dropout(config.dropout))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: [batch, input_dim] → h: [batch, hidden_dim]"""
        return self.net(x)


# ---------------------------------------------------------------------------
# Predictor heads
# ---------------------------------------------------------------------------

class _PredictorHeads(nn.Module):
    """K independent linear predictor heads, one per regime / trading pattern.

    Each head outputs a scalar return prediction for its assigned regime.
    """

    def __init__(self, config: TRAConfig):
        super().__init__()
        self.heads = nn.ModuleList([
            nn.Sequential(
                nn.Linear(config.hidden_dim, config.hidden_dim // 2, bias=False),
                nn.BatchNorm1d(config.hidden_dim // 2),
                nn.GELU(),
                nn.Dropout(config.dropout),
                nn.Linear(config.hidden_dim // 2, 1),
            )
            for _ in range(config.num_regimes)
        ])

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        """h: [batch, hidden_dim] → preds: [batch, K]"""
        return torch.cat([head(h) for head in self.heads], dim=1)


# ---------------------------------------------------------------------------
# Regime router
# ---------------------------------------------------------------------------

class _RegimeRouter(nn.Module):
    """Classifies each sample into one of K regimes using Gumbel-Softmax.

    At inference time uses argmax for discrete assignment.
    """

    def __init__(self, config: TRAConfig):
        super().__init__()
        self.num_regimes = config.num_regimes
        self.classifier = nn.Sequential(
            nn.Linear(config.hidden_dim, config.hidden_dim // 2, bias=False),
            nn.BatchNorm1d(config.hidden_dim // 2),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim // 2, config.num_regimes),
        )

    def forward(
        self,
        h: torch.Tensor,
        temperature: float = 1.0,
        hard: bool = False,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Route each sample to a regime.

        Parameters
        ----------
        h : Tensor [batch, hidden_dim]
            Latent representation from the backbone.
        temperature : float
            Gumbel-Softmax temperature.
        hard : bool
            If True, return straight-through one-hot. Use at inference.

        Returns
        -------
        routing_weights : Tensor [batch, K]
            Soft assignment probabilities (or one-hot when hard=True).
        regime_ids : Tensor [batch]
            Integer regime index per sample.
        """
        logits = self.classifier(h)  # [batch, K]
        routing_weights = F.gumbel_softmax(logits, tau=temperature, hard=hard, dim=-1)
        regime_ids = routing_weights.argmax(dim=-1)  # [batch]
        return routing_weights, regime_ids


# ---------------------------------------------------------------------------
# Full TRA model
# ---------------------------------------------------------------------------

class TRARouter(nn.Module):
    """Temporal Routing Adaptor — lightweight regime classifier for stocks.

    Routes each stock to one of K regimes, each with its own predictor head.
    Returns regime_id, confidence, and the blended final prediction.

    Parameters
    ----------
    config : TRAConfig
        Model hyperparameters.
    regime_labels : list of str
        Human-readable labels for each regime.
    """

    REGIME_LABELS = [
        "Low Vol / Trending",
        "Neutral",
        "High Vol / Mean-Reversion",
    ]

    def __init__(
        self,
        config: Optional[TRAConfig] = None,
        regime_labels: Optional[list[str]] = None,
    ):
        super().__init__()
        self.config = config or TRAConfig()
        self.regime_labels = regime_labels or self.REGIME_LABELS[: self.config.num_regimes]

        self.backbone = _Backbone(self.config)
        self.predictors = _PredictorHeads(self.config)
        self.router = _RegimeRouter(self.config)

        self._init_weights()

    def _init_weights(self):
        """Kaiming uniform init for Linear layers, unit init for BatchNorm."""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_uniform_(m.weight, a=math.sqrt(5))
                if m.bias is not None:
                    fan_in, _ = nn.init._calculate_fan_in_and_fan_out(m.weight)
                    bound = 1.0 / math.sqrt(fan_in) if fan_in > 0 else 0.0
                    nn.init.uniform_(m.bias, -bound, bound)
            elif isinstance(m, nn.BatchNorm1d):
                nn.init.constant_(m.weight, 1.0)
                nn.init.constant_(m.bias, 0.0)

    def forward(
        self,
        x: torch.Tensor,
        temperature: Optional[float] = None,
        hard: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """Forward pass.

        Parameters
        ----------
        x : Tensor [batch, 158]
            Alpha158 feature vectors (raw or normalized).
        temperature : float, optional
            Gumbel-Softmax temperature. Falls back to config.temperature.
        hard : bool
            If True, use straight-through one-hot routing (inference mode).

        Returns
        -------
        dict with keys:
            regime_id       — Tensor [batch] int in [0, K-1]
            confidence      — Tensor [batch] max routing probability
            all_preds       — Tensor [batch, K] raw predictor outputs
            final_pred      — Tensor [batch] softmax-weighted ensemble prediction
            routing_weights — Tensor [batch, K] routing probabilities
        """
        temp = temperature if temperature is not None else self.config.temperature

        h = self.backbone(x)                              # [B, hidden_dim]
        all_preds = self.predictors(h)                     # [B, K]
        routing_weights, regime_ids = self.router(h, temp, hard=hard)  # [B, K], [B]

        # Weighted blend: p̂_i = Σ_k q_{i,k} * ŷ_{i,k}
        final_pred = (routing_weights * all_preds).sum(dim=1)  # [B]

        # Confidence = max routing probability
        confidence = routing_weights.max(dim=1).values        # [B]

        return {
            "regime_id": regime_ids,
            "confidence": confidence,
            "all_preds": all_preds,
            "final_pred": final_pred,
            "routing_weights": routing_weights,
        }

    @torch.no_grad()
    def predict(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """Inference-mode forward pass (hard routing, no gradients).

        Parameters
        ----------
        x : Tensor [batch, 158]

        Returns
        -------
        Same dict as forward() but with hard=True routing.
        """
        was_training = self.training
        self.eval()
        try:
            return self.forward(x, temperature=0.1, hard=True)
        finally:
            if was_training:
                self.train()

    def get_regime_label(self, regime_id: int) -> str:
        """Return human-readable label for a regime index."""
        if 0 <= regime_id < len(self.regime_labels):
            return self.regime_labels[regime_id]
        return f"Regime-{regime_id}"

    @property
    def num_regimes(self) -> int:
        return self.config.num_regimes

    @property
    def input_dim(self) -> int:
        return self.config.input_dim
