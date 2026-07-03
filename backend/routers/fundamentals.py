from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from models.pydantic_fundamentals import (
    FinancialMetrics, Shareholding, CorporateActionDTO, ValuationMetrics, RiskSignalDTO
)
import services.fundamentals as fundamentals_service
from core.entitlement_gate import require_entitlement

router = APIRouter(prefix="/fundamentals", tags=["Fundamentals"])
router_v1 = APIRouter(prefix="/api/v1/fundamentals", tags=["Fundamentals"])

# ── Core routes (prefix: /fundamentals) ──────────────────────────────────────

@router.get("/{ticker}/financials", response_model=List[FinancialMetrics])
@router_v1.get("/{ticker}/financials", response_model=List[FinancialMetrics])
def get_financials_endpoint(ticker: str):
    return fundamentals_service.get_financials(ticker.upper())

@router.get("/{ticker}/shareholding", response_model=List[Shareholding])
@router_v1.get("/{ticker}/shareholding", response_model=List[Shareholding])
def get_shareholding_endpoint(ticker: str):
    return fundamentals_service.get_shareholding(ticker.upper())

@router.get("/{ticker}/corporate-actions", response_model=List[CorporateActionDTO])
@router_v1.get("/{ticker}/corporate-actions", response_model=List[CorporateActionDTO])
def get_corporate_actions_endpoint(ticker: str):
    return fundamentals_service.get_corporate_actions(ticker.upper())

@router.get("/{ticker}/valuation", response_model=ValuationMetrics)
@router_v1.get("/{ticker}/valuation", response_model=ValuationMetrics)
def get_valuation_endpoint(ticker: str, user_id: int = Depends(require_entitlement("comprehensive_stock_insights"))):
    """
    Gated behind the "comprehensive_stock_insights" entitlement (pro tier or higher) —
    see services/entitlement_service.py / core/entitlement_gate.py.
    """
    val = fundamentals_service.get_valuation(ticker.upper())
    if not val:
        raise HTTPException(status_code=404, detail="Valuation not found")
    return val

@router.get("/{ticker}/risk-signals", response_model=List[RiskSignalDTO])
@router_v1.get("/{ticker}/risk-signals", response_model=List[RiskSignalDTO])
def get_risk_signals_endpoint(ticker: str, user_id: int = Depends(require_entitlement("swot_analysis"))):
    """
    Gated behind the "swot_analysis" entitlement (pro tier or higher) —
    see services/entitlement_service.py / core/entitlement_gate.py.
    """
    return fundamentals_service.get_risk_signals(ticker.upper())

# ── Api v1 aliases with default ticker (for test compatibility) ──────────────

@router_v1.get("/financials")
def get_financials_v1():
    return fundamentals_service.get_financials("RELIANCE.NS")

@router_v1.get("/shareholding")
def get_shareholding_v1():
    return fundamentals_service.get_shareholding("RELIANCE.NS")

@router_v1.get("/corporate-actions")
def get_corporate_actions_v1():
    return fundamentals_service.get_corporate_actions("RELIANCE.NS")

@router_v1.get("/valuation")
def get_valuation_v1(user_id: int = Depends(require_entitlement("comprehensive_stock_insights"))):
    return fundamentals_service.get_valuation("RELIANCE.NS")

@router_v1.get("/risk-signals")
def get_risk_signals_v1(user_id: int = Depends(require_entitlement("swot_analysis"))):
    return fundamentals_service.get_risk_signals("RELIANCE.NS")
