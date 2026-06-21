"""
TRAModel — Temporal Routing Adaptor (KDD 2021, Microsoft Research).

A lightweight PyTorch module that wraps any backbone feature extractor
with K parallel linear predictor heads and a learned router that dispatches
each sample to the most appropriate predictor.

Architecture:
  1. Raw features x_i [seq_len, 158] -> backbone GRU -> latent h_i [hidden_dim]
  2. h_i -> K linear predictors -> K predictions [batch, K]
  3. h_i + temporal error history -> router -> Gumbel-Softmax routing weights
  4. Final: p_i = sum_k(routing_k * pred_k)  — scalar stock return prediction

Reference: Hengxu Lin et al., "Learning Multiple Stock Trading Patterns
with Temporal Routing Adaptor and Optimal Transport", KDD 2021.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class TRAModel(nn.Module):
    """Temporal Routing Adaptor for stock return prediction.

    Args:
        input_dim: Number of input features (158 for Alpha158).
        hidden_dim: Latent representation dimension.
        num_layers: GRU backbone layers.
        num_states: Number of trading pattern predictors (K).
        seq_len: Input sequence length.
        dropout: Dropout rate.
    """

    def __init__(
        self,
        input_dim: int = 158,
        hidden_dim: int = 64,
        num_layers: int = 2,
        num_states: int = 3,
        seq_len: int = 60,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()

        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.num_states = num_states
        self.seq_len = seq_len

        # ── Backbone: GRU feature extractor ────────────────────────────────
        self.backbone = nn.GRU(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        # ── K parallel predictor heads ─────────────────────────────────────
        self.predictors = nn.ModuleList([
            nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim // 2, 1),
            )
            for _ in range(num_states)
        ])

        # ── Router: dispatches samples to the best predictor ───────────────
        # Input: h_i (hidden_dim) + hist_errors_i (num_states)
        router_input_dim = hidden_dim + num_states
        self.router = nn.Sequential(
            nn.Linear(router_input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, num_states),
        )

        # ── RNN for temporal error history ─────────────────────────────────
        self.error_rnn = nn.GRU(
            input_size=num_states,
            hidden_size=num_states,
            num_layers=1,
            batch_first=True,
        )

    def forward(
        self,
        x: torch.Tensor,
        hist_errors: torch.Tensor | None = None,
        temperature: float = 0.1,
        hard: bool = False,
    ) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Input features [batch, seq_len, input_dim].
            hist_errors: Historical prediction errors per state [batch, num_states].
                         Pass zeros for cold start.
            temperature: Gumbel-Softmax temperature.
            hard: If True, use straight-through Gumbel-Softmax (argmax backward).

        Returns:
            Scalar prediction per sample [batch].
        """
        batch_size = x.size(0)

        if hist_errors is None:
            hist_errors = torch.zeros(batch_size, self.num_states, device=x.device)

        # 1. Backbone: GRU feature extraction
        _, h_n = self.backbone(x)  # h_n: [num_layers, batch, hidden_dim]
        h_i = h_n[-1]  # last layer: [batch, hidden_dim]

        # 2. K predictor heads -> K scalar predictions per sample
        all_preds = torch.stack(
            [pred(h_i).squeeze(-1) for pred in self.predictors], dim=1
        )  # [batch, K]

        # 3. Router: h_i + hist_errors -> logits -> Gumbel-Softmax weights
        router_input = torch.cat([h_i, hist_errors], dim=-1)  # [batch, hidden+K]
        logits = self.router(router_input)  # [batch, K]
        routing_weights = F.gumbel_softmax(logits, tau=temperature, hard=hard, dim=-1)

        # 4. Weighted combination
        output = (routing_weights * all_preds).sum(dim=1)  # [batch]

        return output
