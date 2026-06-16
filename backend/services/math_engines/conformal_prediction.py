"""Conformal prediction bounds engine."""
from __future__ import annotations
import math
from typing import Any
from services.math_engines.protocol import InferenceEngine


class ConformalPredictionEngine(InferenceEngine):
    
    @classmethod
    def name(cls) -> str:
        return "conformal_prediction"
    
    @classmethod
    def tags(cls) -> set[str]:
        return {"confidence_modifier", "risk_metric", "quantitative"}
    
    def compute(self, ticker: str, data: dict, session: Any = None) -> dict:
        prices = data.get("prices", [])
        alpha = data.get("alpha", 0.1)
        horizon = data.get("horizon_days", 63)
        
        if len(prices) < 60:
            return {"status": "error", "error": f"Need >= 60 days of prices, got {len(prices)}"}
        
        try:
            returns = [math.log(prices[i] / prices[i-1]) for i in range(1, len(prices))]
            daily_vol = (sum((r - sum(returns)/len(returns))**2 for r in returns) / (len(returns)-1)) ** 0.5
            projected_vol = daily_vol * math.sqrt(horizon)
            z_score = 1.645  # 95% one-sided
            drift = sum(returns) / len(returns) * horizon
            
            current = prices[-1]
            upper = current * math.exp(drift + z_score * projected_vol)
            lower = current * math.exp(drift - z_score * projected_vol)
            
            return {
                "status": "ok",
                "output": {
                    "current_price": current,
                    f"upper_{horizon}d": round(upper, 2),
                    f"lower_{horizon}d": round(lower, 2),
                    "daily_volatility_pct": round(daily_vol * 100, 2),
                    "projected_volatility_pct": round(projected_vol * 100, 2),
                    "confidence_level": f"{(1 - alpha) * 100:.0f}%",
                }
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
