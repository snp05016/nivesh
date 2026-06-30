"""Minskyan financial instability risk engine."""
from __future__ import annotations
import math
from typing import Any, List, Dict, Optional
from services.math_engines.protocol import InferenceEngine
from pydantic import BaseModel

class MinskyRiskOutput(BaseModel):
    minsky_score: float
    minsky_stage: str
    risk_level: str
    fii_flow_average: float
    dii_flow_average: float
    flow_imbalance: float

class MinskyRiskResponse(BaseModel):
    status: str
    error: Optional[str] = None
    output: Optional[MinskyRiskOutput] = None

class MinskyRiskEngine(InferenceEngine):
    
    @classmethod
    def name(cls) -> str:
        return "minsky_risk"
    
    @classmethod
    def tags(cls) -> set[str]:
        return {"confidence_modifier", "risk_metric"}
    
    def compute(self, ticker: str, data: dict, session: Any = None) -> MinskyRiskResponse:
        fii_flows = data.get("fii_flows", [])
        dii_flows = data.get("dii_flows", [])
        
        if not fii_flows or not dii_flows:
            return MinskyRiskResponse(status="error", error="No FII/DII flow data provided")
        
        try:
            fii_ma = sum(fii_flows) / len(fii_flows) if fii_flows else 0
            dii_ma = sum(dii_flows) / len(dii_flows) if dii_flows else 0
            flow_imbalance = abs(fii_ma - dii_ma) / (abs(fii_ma) + abs(dii_ma) + 1)
            
            fii_vol = (sum((f - fii_ma)**2 for f in fii_flows) / len(fii_flows)) ** 0.5
            dii_vol = (sum((d - dii_ma)**2 for d in dii_flows) / len(dii_flows)) ** 0.5
            
            minsky_score = min(1.0, flow_imbalance * 0.7 + (fii_vol / (abs(fii_ma)+1)) * 0.3)
            
            if minsky_score < 0.3:
                stage = "Hedge (stable)"
                risk = "low"
            elif minsky_score < 0.6:
                stage = "Speculative (transition)"
                risk = "medium"
            else:
                stage = "Ponzi (crisis-prone)"
                risk = "high"
            
            return MinskyRiskResponse(
                status="ok",
                output=MinskyRiskOutput(
                    minsky_score=round(minsky_score, 4),
                    minsky_stage=stage,
                    risk_level=risk,
                    fii_flow_average=round(fii_ma, 4),
                    dii_flow_average=round(dii_ma, 4),
                    flow_imbalance=round(flow_imbalance, 4),
                )
            )
        except Exception as e:
            return MinskyRiskResponse(status="error", error=str(e))
