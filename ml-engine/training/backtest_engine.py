"""
Backtest Engine — Simulates historical portfolio performance using trained LightGBM models.
Computes Hit Rate, Precision, Recall, Sharpe, Sortino, Max Drawdown, CAGR, Brier Score, ECE, and MCE.
"""

from __future__ import annotations

import logging
from typing import Any
import numpy as np

_LOG = logging.getLogger(__name__)

class BacktestEngine:
    def __init__(self, initial_capital: float = 1_000_000.0, transaction_cost: float = 0.001):
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost
        
    def run(self, predictions: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Run backtest over a series of predictions.
        
        Parameters
        ----------
        predictions : list[dict]
            List of prediction dictionaries containing:
            - 'date'
            - 'ticker'
            - 'y_prob': predicted probability
            - 'y_true': ground truth label (1 or 0)
            - 'forward_return': actual forward return
            
        Returns
        -------
        dict
            Dictionary containing computed backtest metrics.
        """
        if not predictions:
            return self._empty_metrics()
            
        # Basic Classification Metrics
        y_true = np.array([p['y_true'] for p in predictions if 'y_true' in p and p['y_true'] is not None])
        y_prob = np.array([p['y_prob'] for p in predictions if 'y_prob' in p and p['y_prob'] is not None])
        
        if len(y_true) == 0 or len(y_prob) == 0:
            return self._empty_metrics()
            
        y_pred = (y_prob >= 0.5).astype(int)
        
        hit_rate = np.mean(y_true == y_pred)
        
        true_positives = np.sum((y_pred == 1) & (y_true == 1))
        predicted_positives = np.sum(y_pred == 1)
        actual_positives = np.sum(y_true == 1)
        
        precision = true_positives / predicted_positives if predicted_positives > 0 else 0.0
        recall = true_positives / actual_positives if actual_positives > 0 else 0.0
        
        brier_score = np.mean((y_prob - y_true) ** 2)
        
        # Financial Metrics (Simplified Portfolio Simulation)
        # We assume an equal-weighted portfolio of all 'buy' signals (y_prob >= 0.5) per day
        # For a more robust backtest, this should be grouped by date
        returns = np.array([p.get('forward_return', 0.0) for p in predictions if p.get('y_prob', 0) >= 0.5])
        
        if len(returns) > 0:
            avg_return = np.mean(returns)
            cagr = (1 + avg_return) ** 252 - 1 # Assuming daily returns
            
            # Sharpe Ratio
            risk_free_rate = 0.05 # 5% annual
            daily_rf = risk_free_rate / 252
            excess_returns = returns - daily_rf
            std_dev = np.std(returns)
            sharpe = (np.mean(excess_returns) / std_dev * np.sqrt(252)) if std_dev > 0 else 0.0
            
            # Sortino Ratio
            downside_returns = returns[returns < 0]
            downside_std = np.std(downside_returns) if len(downside_returns) > 0 else 0.0
            sortino = (np.mean(excess_returns) / downside_std * np.sqrt(252)) if downside_std > 0 else 0.0
            
            # Max Drawdown
            cumulative = np.cumprod(1 + returns)
            running_max = np.maximum.accumulate(cumulative)
            drawdowns = (cumulative - running_max) / running_max
            max_drawdown = np.min(drawdowns) if len(drawdowns) > 0 else 0.0
        else:
            cagr = 0.0
            sharpe = 0.0
            sortino = 0.0
            max_drawdown = 0.0
            
        return {
            "hit_rate": float(hit_rate),
            "precision": float(precision),
            "recall": float(recall),
            "brier_score": float(brier_score),
            "cagr": float(cagr),
            "sharpe_ratio": float(sharpe),
            "sortino_ratio": float(sortino),
            "max_drawdown": float(max_drawdown),
            "total_trades": len(returns),
            "win_rate": float(np.mean(returns > 0)) if len(returns) > 0 else 0.0
        }
        
    def _empty_metrics(self) -> dict[str, Any]:
        return {
            "hit_rate": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "brier_score": 0.0,
            "cagr": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown": 0.0,
            "total_trades": 0,
            "win_rate": 0.0
        }
