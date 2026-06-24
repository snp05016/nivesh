from fastapi import APIRouter, HTTPException, status
from typing import List
from models.pydantic_fundamentals import (
    FinancialMetrics, Shareholding, CorporateActionDTO, ValuationMetrics, RiskSignalDTO
)
import services.fundamentals as fundamentals_service

router = APIRouter(prefix="/fundamentals", tags=["Fundamentals"])

@router.get("/{ticker}/financials", response_model=List[FinancialMetrics])
def get_financials_endpoint(ticker: str):
    return fundamentals_service.get_financials(ticker.upper())

@router.get("/{ticker}/shareholding", response_model=List[Shareholding])
def get_shareholding_endpoint(ticker: str):
    return fundamentals_service.get_shareholding(ticker.upper())

@router.get("/{ticker}/corporate-actions", response_model=List[CorporateActionDTO])
def get_corporate_actions_endpoint(ticker: str):
    return fundamentals_service.get_corporate_actions(ticker.upper())

@router.get("/{ticker}/valuation", response_model=ValuationMetrics)
def get_valuation_endpoint(ticker: str):
    val = fundamentals_service.get_valuation(ticker.upper())
    if not val:
        raise HTTPException(status_code=404, detail="Valuation not found")
    return val

@router.get("/{ticker}/risk-signals", response_model=List[RiskSignalDTO])
def get_risk_signals_endpoint(ticker: str):
    return fundamentals_service.get_risk_signals(ticker.upper())
