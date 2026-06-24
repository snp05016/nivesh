from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from database import get_session
from sqlalchemy.orm import Session
from models.pydantic_fundamentals import (
    FinancialMetrics, Shareholding, CorporateActionDTO, ValuationMetrics, RiskSignalDTO
)
import services.fundamentals as fundamentals_service

router = APIRouter(prefix="/fundamentals", tags=["Fundamentals"])

def _get_db():
    with get_session() as session:
        yield session

@router.get("/{ticker}/financials", response_model=List[FinancialMetrics])
def get_financials_endpoint(ticker: str, db: Session = Depends(_get_db)):
    return fundamentals_service.get_financials(db, ticker.upper())

@router.get("/{ticker}/shareholding", response_model=List[Shareholding])
def get_shareholding_endpoint(ticker: str, db: Session = Depends(_get_db)):
    return fundamentals_service.get_shareholding(db, ticker.upper())

@router.get("/{ticker}/corporate-actions", response_model=List[CorporateActionDTO])
def get_corporate_actions_endpoint(ticker: str, db: Session = Depends(_get_db)):
    return fundamentals_service.get_corporate_actions(db, ticker.upper())

@router.get("/{ticker}/valuation", response_model=ValuationMetrics)
def get_valuation_endpoint(ticker: str, db: Session = Depends(_get_db)):
    val = fundamentals_service.get_valuation(db, ticker.upper())
    if not val:
        raise HTTPException(status_code=404, detail="Valuation not found")
    return val

@router.get("/{ticker}/risk-signals", response_model=List[RiskSignalDTO])
def get_risk_signals_endpoint(ticker: str, db: Session = Depends(_get_db)):
    return fundamentals_service.get_risk_signals(db, ticker.upper())
