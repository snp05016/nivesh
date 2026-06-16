"""Dynamic Time Warping pattern matching engine."""
from __future__ import annotations
import math
from typing import Any
from services.math_engines.protocol import InferenceEngine


class DTWPatternEngine(InferenceEngine):
    
    _TEMPLATES = {
        "head_and_shoulders": [1.0, 1.1, 1.2, 1.15, 1.2, 1.15, 1.1, 1.05, 0.95, 0.85],
        "inverse_head_shoulders": [0.85, 0.95, 0.85, 0.95, 0.85, 1.0, 1.1, 1.15, 1.2, 1.3],
        "double_top": [1.0, 1.05, 1.1, 1.08, 1.05, 1.1, 1.08, 1.03, 1.0, 0.97],
        "double_bottom": [1.0, 0.97, 0.95, 0.97, 1.0, 0.97, 0.95, 0.97, 1.02, 1.05],
        "ascending_triangle": [1.0, 1.02, 1.04, 1.06, 1.05, 1.06, 1.05, 1.06, 1.05, 1.06],
        "descending_triangle": [1.0, 0.98, 0.96, 0.94, 0.95, 0.94, 0.95, 0.94, 0.95, 0.94],
    }
    
    _PATTERN_DIRECTION = {
        "head_and_shoulders": "BEARISH",
        "inverse_head_shoulders": "BULLISH",
        "double_top": "BEARISH",
        "double_bottom": "BULLISH",
        "ascending_triangle": "BULLISH",
        "descending_triangle": "BEARISH",
    }
    
    @classmethod
    def name(cls) -> str:
        return "dtw_pattern_matching"
    
    @classmethod
    def tags(cls) -> set[str]:
        return {"technical", "pattern_detection"}
    
    @staticmethod
    def _dtw_distance(s1: list[float], s2: list[float]) -> float:
        n, m = len(s1), len(s2)
        dtw = [[float('inf')] * (m+1) for _ in range(n+1)]
        dtw[0][0] = 0
        for i in range(1, n+1):
            for j in range(1, m+1):
                cost = abs(s1[i-1] - s2[j-1])
                dtw[i][j] = cost + min(dtw[i-1][j], dtw[i][j-1], dtw[i-1][j-1])
        return dtw[n][m]
    
    def compute(self, ticker: str, data: dict, session: Any = None) -> dict:
        prices = data.get("prices", [])
        if len(prices) < 15:
            return {"status": "error", "error": f"Need >= 15 price points, got {len(prices)}"}
        
        try:
            recent = prices[-15:]
            baseline = recent[0]
            normalized = [p / baseline for p in recent]
            
            matches = []
            for name, template in self._TEMPLATES.items():
                dist = self._dtw_distance(normalized, template)
                matches.append({"pattern": name, "distance": round(dist, 4),
                               "direction": self._PATTERN_DIRECTION.get(name, "NEUTRAL")})
            
            matches.sort(key=lambda m: m["distance"])
            best = matches[0]
            
            return {
                "status": "ok",
                "output": {
                    "detected_pattern": best["pattern"] if best["distance"] < 2.0 else "no_clear_pattern",
                    "confidence": "high" if best["distance"] < 1.0 else "medium" if best["distance"] < 2.0 else "low",
                    "direction": best["direction"],
                    "top_matches": matches[:3],
                }
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
