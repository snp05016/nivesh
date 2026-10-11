from typing import Any, List, Optional
from sqlalchemy.orm import Session
from database import get_session
from models.db_models import (
    CompanyFinancial, ShareholdingPattern, CorporateAction, CompanyValuation, RiskSignal
)
from models.pydantic_fundamentals import (
    FinancialMetrics, Shareholding, CorporateActionDTO, ValuationMetrics, RiskSignalDTO
)
from schemas.stock_fundamentals import (
    FinancialLineItem, FinancialPeriod, FinancialStatementResponse,
    ShareholderCategory, ShareholdingQuarter, ShareholdingResponse,
    CorporateAction as SchemaCorporateAction, CorporateActionsResponse,
    ValuationSnapshot, ValuationResponse,
    RiskSignal as SchemaRiskSignal, RiskSignalsResponse,
)
from helpers import format_indian_currency, _ban_western_scale
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


# ── v1 query-style builders (schemas.stock_fundamentals, the iOS DTO family) ──
# Built only from the DB tables above: unknown optionals stay None, unknown
# lists stay []. Each returns None when the ticker has no rows (router -> 404).
# Rows are typed Any: the legacy Column() declarations make pyright see
# instance attributes as Column objects.

_CRORE = 1e7
_SEVERITY_SCORE = {"LOW": 25.0, "MEDIUM": 50.0, "HIGH": 75.0, "CRITICAL": 100.0}


def _ticker_keys(ticker: str, exchange: str = "NSE") -> tuple:
    """Stored-ticker spellings for a bare symbol: 'TCS' and 'TCS.NS' (or '.BO' for BSE)."""
    suffix = ".BO" if exchange.upper() == "BSE" else ".NS"
    return (ticker, f"{ticker}{suffix}")


def _period_index(period: str) -> Optional[int]:
    """'Q1_2026' -> 2026*4+0, 'Q1 FY26' -> 26*4+0, 'FY26' -> 26; None when unparseable."""
    p = period.upper().replace(" ", "_")
    try:
        if p.startswith("FY"):
            return int(p[2:])
        if p.startswith("Q"):
            q, year = p[1:].split("_", 1)
            return int(year.removeprefix("FY")) * 4 + int(q) - 1
    except ValueError:
        return None
    return None


def _pct_change(cur: Optional[float], prev: Optional[float]) -> Optional[float]:
    if cur is None or prev is None or prev == 0:
        return None
    return round((cur - prev) / abs(prev) * 100, 2)


def get_financial_statement_v1(ticker: str, exchange: str = "NSE", period_type: str = "QUARTERLY",
                               consolidation: str = "STANDALONE", periods: int = 8) -> Optional[FinancialStatementResponse]:
    annual = period_type.upper() in ("ANNUAL", "YEARLY")
    with get_session() as session:
        records: List[Any] = session.query(CompanyFinancial).filter(CompanyFinancial.ticker.in_(_ticker_keys(ticker, exchange))).all()
        rows = {}
        for r in records:
            idx = _period_index(r.period)
            if idx is not None and r.period.upper().startswith("FY") == annual:
                rows[idx] = r
    if not rows:
        return None
    ordered = sorted(rows, reverse=True)[:periods]
    labels = {i: rows[i].period.replace("_", " ") for i in rows}
    yoy_step = 1 if annual else 4

    def line_item(label, group, attr, scale=1.0, is_percentage=False):
        def val(i):
            v = getattr(rows[i], attr) if i in rows else None
            return round(v / scale, 2) if v is not None else None
        values, qoq, yoy = {}, {}, {}
        for i in ordered:
            v = val(i)
            if v is None:
                continue
            values[labels[i]] = v
            # iOS decodes these maps as [String: Double], so omit unknowns instead of sending null.
            if not annual and (c := _pct_change(v, val(i - 1))) is not None:
                qoq[labels[i]] = c
            if (c := _pct_change(v, val(i - yoy_step))) is not None:
                yoy[labels[i]] = c
        return FinancialLineItem(label=label, group=group, values=values, qoq_change_pct=qoq,
                                 yoy_change_pct=yoy, is_percentage=is_percentage)

    return FinancialStatementResponse(
        ticker=ticker,
        period_type="ANNUAL" if annual else "QUARTERLY",
        consolidation=consolidation.upper(),
        periods=[FinancialPeriod(label=labels[i], end_date="") for i in ordered],
        line_items=[
            line_item("Revenue", "income_statement", "revenue", _CRORE),
            line_item("Net Profit", "income_statement", "net_income", _CRORE),
            line_item("EPS", "ratios", "eps"),
            line_item("Operating Margin", "ratios", "operating_margin", is_percentage=True),
            line_item("Free Cash Flow", "cash_flow", "free_cash_flow", _CRORE),
        ],
        available_periods=[labels[i] for i in ordered],
    )


def get_shareholding_v1(ticker: str, exchange: str = "NSE") -> Optional[ShareholdingResponse]:
    with get_session() as session:
        records: List[Any] = session.query(ShareholdingPattern).filter(ShareholdingPattern.ticker.in_(_ticker_keys(ticker, exchange))).all()
        records = sorted(records, key=lambda r: _period_index(r.quarter) or 0, reverse=True)
        if not records:
            return None
        trend = []
        for r in records:
            parts = [r.promoter_pct or 0.0, r.fii_pct or 0.0, r.dii_pct or 0.0, r.public_pct or 0.0]
            trend.append(ShareholdingQuarter(
                quarter=r.quarter.replace("_", " "), promoter_pct=parts[0], fii_pct=parts[1],
                dii_pct=parts[2], public_pct=parts[3], others_pct=round(max(0.0, 100.0 - sum(parts)), 2),
            ))
        latest, prev = records[0], (records[1] if len(records) > 1 else None)
    categories = []
    for name, attr in (("PROMOTER", "promoter_pct"), ("FII", "fii_pct"), ("DII", "dii_pct"), ("PUBLIC", "public_pct")):
        cur = getattr(latest, attr)
        if cur is None:
            continue
        before = getattr(prev, attr) if prev is not None else None
        categories.append(ShareholderCategory(
            name=name, current_pct=cur,
            qoq_change_bps=round((cur - before) * 100, 1) if before is not None else None,
        ))
    pledge_prev = prev.pledged_pct if prev is not None else None
    return ShareholdingResponse(
        ticker=ticker,
        latest_quarter=trend[0].quarter,
        available_quarters=[q.quarter for q in trend],
        categories=categories,
        top_holders=[],
        promoter_pledge_pct=latest.pledged_pct,
        promoter_pledge_qoq_change=(round(latest.pledged_pct - pledge_prev, 2)
                                    if latest.pledged_pct is not None and pledge_prev is not None else None),
        holding_trend=trend,
    )


def _action_type(purpose: str) -> str:
    p = purpose.upper()
    for kind in ("SPLIT", "BONUS", "RIGHTS", "BUYBACK"):
        if kind in p:
            return kind
    return "DIVIDEND" if "DIVIDEND" in p else "OTHER"


def get_corporate_actions_v1(ticker: str, exchange: str = "NSE") -> Optional[CorporateActionsResponse]:
    with get_session() as session:
        records: List[Any] = (session.query(CorporateAction)
                   .filter(CorporateAction.ticker.in_(_ticker_keys(ticker, exchange)))
                   .order_by(CorporateAction.ex_date.desc()).all())
        if not records:
            return None
        actions = [SchemaCorporateAction(
            type=_action_type(r.purpose), announcement_date="", ex_date=r.ex_date,
            record_date=r.record_date or "", details=r.purpose, amount=r.dividend_amount,
        ) for r in records]
    return CorporateActionsResponse(ticker=ticker, actions=actions, upcoming=[])


def get_valuation_v1(ticker: str, exchange: str = "NSE") -> Optional[ValuationResponse]:
    with get_session() as session:
        r: Any = (session.query(CompanyValuation)
             .filter(CompanyValuation.ticker.in_(_ticker_keys(ticker, exchange)))
             .order_by(CompanyValuation.date.desc()).first())
        if r is None:
            return None
        snapshot = ValuationSnapshot(
            ticker=ticker, pe_current=r.current_pe, pb_current=r.pb_ratio, ev_ebitda=r.ev_ebitda,
            # ponytail: schema requires a float; 0.0 means "not reported" until the field turns Optional on both ends.
            market_cap_crores=round(r.market_cap / _CRORE, 2) if r.market_cap is not None else 0.0,
            earnings_yield=round(100.0 / r.current_pe, 2) if r.current_pe else None,
        )
    return ValuationResponse(ticker=ticker, snapshot=snapshot, pe_band_data=[], peer_comparison=[])


def get_risk_signals_v1(ticker: str, exchange: str = "NSE") -> RiskSignalsResponse:
    """Never None: no stored signals means an empty list with score 0."""
    with get_session() as session:
        records: List[Any] = (session.query(RiskSignal)
                   .filter(RiskSignal.ticker.in_(_ticker_keys(ticker, exchange)))
                   .order_by(RiskSignal.date.desc()).all())
        signals = [SchemaRiskSignal(
            type=r.signal_type.upper(), severity=r.severity.upper(),
            title=r.signal_type.replace("_", " ").title(), description=r.description, detected_at=r.date,
        ) for r in records]
    score = max((_SEVERITY_SCORE.get(s.severity, 0.0) for s in signals), default=0.0)
    return RiskSignalsResponse(ticker=ticker, overall_risk_score=score, signals=signals)
