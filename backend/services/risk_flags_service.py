"""Risk flags for a stock the user holds (spec_ai 3.4, concentration checks).

Post-trade only: a stock the user is just browsing gets no flag. Everything is computed from
the user's holdings and the stored research reports; no network call and no LLM call.
"""
import re
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func

from core.feature_flags import is_enabled
from database import get_session
from models.db_models import Portfolio, ResearchReportRow
from repositories.research_repo import normalize_symbol

STOCK_FLAG_PCT = 20.0
SECTOR_FLAG_PCT = 40.0
MAX_FLAGS = 3
PRICE_MAX_AGE_DAYS = 5
_SYMBOL_RE = re.compile(r"^[A-Z0-9&-]{1,20}$")
_SOURCE = "Your Nivesh holdings"
_IST = ZoneInfo("Asia/Kolkata")


def _fmt_date(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


def risk_flags(user_id: int, symbol: str, *, today: date | None = None) -> dict:
    sym = normalize_symbol(symbol)
    if not _SYMBOL_RE.match(sym):
        raise ValueError("invalid symbol")
    today = today or datetime.now(_IST).date()
    checks: list[str] = []
    flags: list[dict] = []
    unavailable: list[dict] = []
    if is_enabled("risk_flags_concentration"):
        checks.append("concentration")
        flags += concentration_flags(user_id, sym, today)
    return {"symbol": sym, "checks": checks, "flags": flags[:MAX_FLAGS], "unavailable": unavailable}


def _latest_reports(db, symbols: list[str]) -> dict[str, ResearchReportRow]:
    """Latest report per symbol in one query; the nightly row wins over others of that date."""
    latest = (db.query(ResearchReportRow.symbol.label("symbol"),
                       func.max(ResearchReportRow.as_of_date).label("d"))
              .filter(ResearchReportRow.symbol.in_(symbols))
              .group_by(ResearchReportRow.symbol).subquery())
    rows = (db.query(ResearchReportRow)
            .join(latest, (ResearchReportRow.symbol == latest.c.symbol)
                  & (ResearchReportRow.as_of_date == latest.c.d))
            .all())
    best: dict[str, ResearchReportRow] = {}
    for row in rows:
        cur = best.get(row.symbol)
        if cur is None or (row.origin == "nightly", row.id) > (cur.origin == "nightly", cur.id):
            best[row.symbol] = row
    return best


def _usable_close(report) -> Decimal | None:
    try:
        close = report["snapshot"]["last_close"]
        if close["status"] == "ok" and close["value"] is not None and float(close["value"]) > 0:
            return Decimal(str(close["value"]))
    except (KeyError, TypeError, ValueError):
        pass
    return None


def concentration_flags(user_id: int, sym: str, today: date) -> list[dict]:
    with get_session() as db:
        rows = [(r.ticker, r.shares, r.buy_price) for r in db.query(Portfolio).filter(
            Portfolio.user_id == user_id,
            Portfolio.group_name == "holdings",
            Portfolio.is_virtual.is_(False),
        ).all()]
        shares: dict[str, Decimal] = {}
        invested: dict[str, Decimal] = {}
        for ticker, qty, buy_price in rows:  # one row per lot, as 'TCS' or 'TCS.NS'
            s = normalize_symbol(ticker)
            if not s:
                continue
            q = Decimal(str(qty or 0))
            shares[s] = shares.get(s, Decimal(0)) + q
            invested[s] = invested.get(s, Decimal(0)) + q * Decimal(str(buy_price or 0))
        held = [s for s in shares if shares[s] > 0]
        if sym not in held:
            return []
        reports = _latest_reports(db, held)
        closes: dict[str, Decimal] = {}
        dates: dict[str, date] = {}
        sectors: dict[str, str | None] = {}
        for s in held:
            row = reports.get(s)
            if row is None:
                continue
            report = row.report_json if isinstance(row.report_json, dict) else {}
            close = _usable_close(report)
            if close is not None:
                closes[s] = close
                dates[s] = row.as_of_date
            sector = report.get("sector")
            sectors[s] = sector.strip() if isinstance(sector, str) and sector.strip() else None

    current = all(s in closes and (today - dates[s]).days <= PRICE_MAX_AGE_DAYS for s in held)
    if current:
        values = {s: shares[s] * closes[s] for s in held}
        basis, basis_date = "current value", min(dates[s] for s in held)
    else:
        values = {s: invested[s] for s in held}
        basis, basis_date = "amount invested", None
    total = sum(values.values(), Decimal(0))
    if total <= 0:
        return []
    as_of = basis_date.isoformat() if basis_date else None
    out: list[dict] = []

    weight = values[sym] / total * 100
    if weight > Decimal(str(STOCK_FLAG_PCT)):
        tail = (f"by current value, using closing prices from {_fmt_date(basis_date)}" if current
                else "by amount invested")
        out.append({
            "id": "holding_concentration",
            "title": "Large share of your holdings",
            "text": f"{sym} is {weight:.1f}% of your holdings {tail}. This line appears when one stock is above 20%.",
            "source": _SOURCE, "source_url": None, "as_of": as_of,
        })

    sector = sectors.get(sym)
    if sector:
        peers = [s for s in held if sectors.get(s) == sector]
        sector_weight = sum((values[s] for s in peers), Decimal(0)) / total * 100
        if len(peers) > 1 and sector_weight > Decimal(str(SECTOR_FLAG_PCT)):
            out.append({
                "id": "sector_concentration",
                "title": "Large share in one sector",
                "text": f"{sector} stocks are {sector_weight:.1f}% of your holdings by {basis}. "
                        "This line appears when one sector is above 40%.",
                "source": _SOURCE, "source_url": None, "as_of": as_of,
            })
    return out
