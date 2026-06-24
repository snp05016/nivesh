from typing import List, Optional
from sqlalchemy.orm import Session
from database import get_session
from models.db_models import (
    CompanyFinancial, ShareholdingPattern, CorporateAction, CompanyValuation, RiskSignal
)
from models.pydantic_fundamentals import (
    FinancialMetrics, Shareholding, CorporateActionDTO, ValuationMetrics, RiskSignalDTO
)
from main import format_indian_currency, _ban_western_scale
import json

def get_financials(ticker: str) -> List[FinancialMetrics]:
    with get_session() as session:
        records = session.query(CompanyFinancial).filter(CompanyFinancial.ticker == ticker).order_by(CompanyFinancial.period.desc()).all()
        results = []
        for r in records:
            results.append(FinancialMetrics(
                period=r.period,
                revenue=format_indian_currency(r.revenue) if r.revenue is not None else None,
                net_income=format_indian_currency(r.net_income) if r.net_income is not None else None,
                eps=r.eps,
                operating_margin=r.operating_margin,
                free_cash_flow=format_indian_currency(r.free_cash_flow) if r.free_cash_flow is not None else None
            ))
        _ban_western_scale(json.dumps([r.model_dump() for r in results]))
        return results

def get_shareholding(ticker: str) -> List[Shareholding]:
    with get_session() as session:
        records = session.query(ShareholdingPattern).filter(ShareholdingPattern.ticker == ticker).order_by(ShareholdingPattern.quarter.desc()).all()
        results = []
        for r in records:
            results.append(Shareholding(
                quarter=r.quarter,
                promoter_pct=r.promoter_pct,
                fii_pct=r.fii_pct,
                dii_pct=r.dii_pct,
                public_pct=r.public_pct,
                pledged_pct=r.pledged_pct
            ))
        _ban_western_scale(json.dumps([r.model_dump() for r in results]))
        return results

def get_corporate_actions(ticker: str) -> List[CorporateActionDTO]:
    with get_session() as session:
        records = session.query(CorporateAction).filter(CorporateAction.ticker == ticker).order_by(CorporateAction.ex_date.desc()).all()
        results = []
        for r in records:
            results.append(CorporateActionDTO(
                ex_date=r.ex_date,
                record_date=r.record_date,
                purpose=r.purpose,
                dividend_amount=r.dividend_amount
            ))
        _ban_western_scale(json.dumps([r.model_dump() for r in results]))
        return results

def get_valuation(ticker: str) -> Optional[ValuationMetrics]:
    with get_session() as session:
        record = session.query(CompanyValuation).filter(CompanyValuation.ticker == ticker).order_by(CompanyValuation.date.desc()).first()
        if record:
            val = ValuationMetrics(
                date=record.date,
                current_pe=record.current_pe,
                forward_pe=record.forward_pe,
                pb_ratio=record.pb_ratio,
                ev_ebitda=record.ev_ebitda,
                market_cap=format_indian_currency(record.market_cap) if record.market_cap is not None else None
            )
            _ban_western_scale(json.dumps(val.model_dump()))
            return val
        return None

def get_risk_signals(ticker: str) -> List[RiskSignalDTO]:
    with get_session() as session:
        records = session.query(RiskSignal).filter(RiskSignal.ticker == ticker).order_by(RiskSignal.date.desc()).all()
        results = []
        for r in records:
            results.append(RiskSignalDTO(
                date=r.date,
                signal_type=r.signal_type,
                severity=r.severity,
                description=r.description
            ))
        _ban_western_scale(json.dumps([r.model_dump() for r in results]))
        return results
