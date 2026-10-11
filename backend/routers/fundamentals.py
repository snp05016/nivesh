from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from models.pydantic_fundamentals import (
    FinancialMetrics, Shareholding, CorporateActionDTO, ValuationMetrics, RiskSignalDTO
)
from schemas.stock_fundamentals import (
    FinancialStatementResponse, ShareholdingResponse, CorporateActionsResponse,
    ValuationResponse, RiskSignalsResponse,
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

# ── Api v1 query-style routes (?ticker=...), used by the iOS stock profile ───
# Response models are the schemas.stock_fundamentals family the iOS DTOs decode.


def _bare_ticker(ticker: str) -> str:
    t = ticker.strip().upper()
    for suffix in (".NS", ".BO"):
        if t.endswith(suffix):
            return t[: -len(suffix)]
    return t


def _or_404(result, kind: str, ticker: str):
    if result is None:
        raise HTTPException(status_code=404, detail=f"No {kind} data for {ticker}")
    return result


@router_v1.get("/financials", response_model=FinancialStatementResponse)
def get_financials_v1(
    ticker: str,
    exchange: str = "NSE",
    period_type: str = "QUARTERLY",
    consolidation: str = "STANDALONE",
    periods: int = Query(8, ge=1, le=20),
):
    t = _bare_ticker(ticker)
    return _or_404(fundamentals_service.get_financial_statement_v1(t, exchange, period_type, consolidation, periods), "financials", t)


@router_v1.get("/shareholding", response_model=ShareholdingResponse)
def get_shareholding_v1(ticker: str, exchange: str = "NSE"):
    t = _bare_ticker(ticker)
    return _or_404(fundamentals_service.get_shareholding_v1(t, exchange), "shareholding", t)


@router_v1.get("/corporate-actions", response_model=CorporateActionsResponse)
def get_corporate_actions_v1(ticker: str, exchange: str = "NSE"):
    t = _bare_ticker(ticker)
    return _or_404(fundamentals_service.get_corporate_actions_v1(t, exchange), "corporate actions", t)


@router_v1.get("/valuation", response_model=ValuationResponse)
def get_valuation_v1(ticker: str, exchange: str = "NSE", user_id: int = Depends(require_entitlement("comprehensive_stock_insights"))):
    t = _bare_ticker(ticker)
    return _or_404(fundamentals_service.get_valuation_v1(t, exchange), "valuation", t)


@router_v1.get("/risk-signals", response_model=RiskSignalsResponse)
def get_risk_signals_v1(ticker: str, exchange: str = "NSE", user_id: int = Depends(require_entitlement("swot_analysis"))):
    return fundamentals_service.get_risk_signals_v1(_bare_ticker(ticker), exchange)
