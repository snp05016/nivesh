"""
Monte-Carlo bootstrap over KNN historical analogues.

Takes the forward-return distribution of analogues already produced by
confidence_engine.py::find_historical_analogues (cosine KNN) and bootstraps
it to estimate:
  - Expected return distribution (mean, median, std)
  - CVaR-99 (tail risk)
  - Probability of positive return

Fills the `monte_carlo_cvar_99` slot the scoring layer already accepts.
No ML models — pure resampling of empirical data.
"""
from __future__ import annotations
import logging
from typing import Any

from services.math_engines.protocol import InferenceEngine

logger = logging.getLogger(__name__)

_N_BOOTSTRAP = 10_000
_CVAR_PERCENTILE = 1  # bottom 1% for CVaR-99


class MonteCarloBootstrapEngine(InferenceEngine):

    @classmethod
    def name(cls) -> str:
        return "monte_carlo_bootstrap"

    @classmethod
    def tags(cls) -> set[str]:
        return {"risk_metric", "quantitative"}

    def compute(self, ticker: str, data: dict, session: Any = None) -> dict:
        """Bootstrap the forward-return distribution from historical analogues.

        data keys:
          - analogue_returns (list[float], required): forward returns from KNN analogues
          - n_bootstrap (int, default 10000): number of bootstrap iterations
        """
        analogue_returns = data.get("analogue_returns", [])

        if not analogue_returns or len(analogue_returns) < 5:
            return {
                "status": "insufficient_data",
                "output": {
                    "monte_carlo_cvar_99": None,
                    "sample_size": len(analogue_returns),
                    "reason": "Need >= 5 analogue returns for bootstrap.",
                },
            }

        try:
            import numpy as np

            returns = np.array(analogue_returns, dtype=np.float64)
            n_boot = data.get("n_bootstrap", _N_BOOTSTRAP)
            rng = np.random.default_rng(seed=42)  # reproducible

            # Bootstrap: resample with replacement and compute mean of each sample
            boot_means = np.array([
                rng.choice(returns, size=len(returns), replace=True).mean()
                for _ in range(n_boot)
            ], dtype=np.float64)

            # Statistics
            mean_return = float(np.mean(boot_means))
            median_return = float(np.median(boot_means))
            std_return = float(np.std(boot_means))

            # CVaR-99: expected value of the worst 1% of outcomes
            sorted_means = np.sort(boot_means)
            cutoff_idx = max(1, int(n_boot * _CVAR_PERCENTILE / 100))
            cvar_99 = float(np.mean(sorted_means[:cutoff_idx]))

            # Probability of positive return
            prob_positive = float(np.mean(boot_means > 0))

            # Confidence interval (2.5th - 97.5th percentile)
            ci_lower = float(np.percentile(boot_means, 2.5))
            ci_upper = float(np.percentile(boot_means, 97.5))

            return {
                "status": "ok",
                "output": {
                    "monte_carlo_cvar_99": round(cvar_99, 4),
                    "expected_return": round(mean_return, 4),
                    "median_return": round(median_return, 4),
                    "return_std": round(std_return, 4),
                    "prob_positive": round(prob_positive, 4),
                    "confidence_interval_95": [round(ci_lower, 4), round(ci_upper, 4)],
                    "n_analogues": len(analogue_returns),
                    "n_bootstrap": n_boot,
                    "method": "bootstrap_resampling",
                },
            }

        except Exception as e:
            logger.warning("[monte_carlo_bootstrap] error: %s", e)
            return {"status": "error", "error": str(e)}
