"""AMFI NAVAll.txt harvester: the real mutual-fund universe and recorded NAV history.

One scheduled harvest (23:30 and 08:10 IST) upserts every scheme, mirrors its ISINs
into the instrument master and records NAV history from today for open Growth
plans and tracked schemes. No backfill and no computed returns: history starts at
launch. Replaces both legacy amfi_nav_harvester copies (ARCH-19); do not revive them.
"""
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

import requests

from config import settings

logger = logging.getLogger(__name__)

AMFI_NAV_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
MIN_ROWS = 5000
HISTORY_MAX_AGE_DAYS = 7
MAX_BODY_BYTES = 20 * 1024 * 1024
_ISIN_RE = re.compile(r"^IN[A-Z0-9]{10}$")
_HEADING_RE = re.compile(r"^(Open Ended|Close Ended|Interval Fund)\s+Schemes?\s*\((.*)\)\s*$", re.IGNORECASE)
_TYPES = {"open ended": "open", "close ended": "close", "interval fund": "interval"}
_NO_NAV = {"N.A.", "#N/A", "N.A", "NA", ""}


@dataclass
class AmfiRow:
    scheme_code: str
    isin_growth: Optional[str]
    isin_reinvest: Optional[str]
    scheme_name: str
    nav: float
    nav_date: date
    amc_name: str
    category: str
    sub_category: Optional[str]
    scheme_type: Optional[str]
    is_direct_plan: bool
    is_growth_plan: bool


def fetch_navall(timeout: int = 60) -> str:
    resp = requests.get(AMFI_NAV_URL, headers={"User-Agent": settings.get_user_agent()}, timeout=timeout)
    resp.raise_for_status()
    if len(resp.content) > MAX_BODY_BYTES:
        raise RuntimeError(f"NAVAll.txt larger than {MAX_BODY_BYTES} bytes")
    return resp.content.decode("utf-8", errors="replace")


def _category(left: str) -> str:
    text = re.sub(r"\s+Scheme$", "", left.strip(), flags=re.IGNORECASE).lower()
    if text.startswith("equity"):
        return "Equity"
    if text.startswith("debt"):
        return "Debt"
    if text.startswith("hybrid"):
        return "Hybrid"
    if text.startswith("solution"):
        return "Solution Oriented"
    return "Other"


def _split_heading(inner: str) -> tuple[str, Optional[str]]:
    if " - " not in inner:
        return "Other", inner.strip()[:50] or None
    left, right = inner.split(" - ", 1)
    return _category(left), right.strip()[:50] or None


def _isin(raw: str) -> Optional[str]:
    value = raw.strip().upper()
    return value if _ISIN_RE.match(value) else None


def parse_navall(text: str) -> list[AmfiRow]:
    """Every valid scheme row of NAVAll.txt with the heading context (type, category) and AMC in force."""
    rows: list[AmfiRow] = []
    scheme_type: Optional[str] = None
    category, sub_category = "Other", None
    amc = ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ";" not in line:
            m = _HEADING_RE.match(line)
            if m:
                scheme_type = _TYPES[m.group(1).lower()]
                category, sub_category = _split_heading(m.group(2))
            else:
                amc = line
            continue
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 6 or not parts[0].isdigit():
            continue
        nav_raw = parts[4].replace(",", "")
        if nav_raw.upper() in _NO_NAV:
            continue
        try:
            nav = float(nav_raw)
            nav_date = datetime.strptime(parts[5], "%d-%b-%Y").date()
        except ValueError:
            continue
        if nav <= 0:
            continue
        name = parts[3]
        lower = name.lower()
        rows.append(AmfiRow(
            scheme_code=parts[0], isin_growth=_isin(parts[1]), isin_reinvest=_isin(parts[2]), scheme_name=name,
            nav=nav, nav_date=nav_date, amc_name=amc, category=category, sub_category=sub_category,
            scheme_type=scheme_type,
            is_direct_plan=re.search(r"\bdirect\b", lower) is not None,
            is_growth_plan=("growth" in lower and not re.search(r"idcw|dividend|bonus", lower)),
        ))
    return rows


def harvest(*, text: Optional[str] = None, today: Optional[date] = None) -> dict:
    """Upsert the AMFI universe, mirror ISINs to instruments and record fresh NAV history. One commit."""
    from core.timeutil import ist_today, utcnow
    from database import get_session
    from models.db_models import DailyPrice, Instrument, MutualFund
    from services import data_flags, instruments
    from services.mutual_fund_service import SAMPLE_SCHEME_CODES

    if not data_flags.enabled("data_mf_universe"):
        return {"skipped": "flag_off"}
    rows = parse_navall(text if text is not None else fetch_navall())
    if len(rows) < MIN_ROWS:
        raise RuntimeError(f"AMFI file too short: {len(rows)} rows (< {MIN_ROWS})")
    today = today or ist_today()
    cutoff = today - timedelta(days=HISTORY_MAX_AGE_DAYS)
    now = utcnow().replace(tzinfo=None)
    counts = {"parsed": len(rows), "funds_inserted": 0, "funds_updated": 0, "history_rows": 0, "deactivated": 0}
    with get_session() as session:
        funds = {f.scheme_code: f for f in session.query(MutualFund).filter(MutualFund.scheme_code.isnot(None))}
        insts = {i.amfi_scheme_code: i for i in
                 session.query(Instrument).filter(Instrument.asset_class == "MF", Instrument.amfi_scheme_code.isnot(None))}
        history = {(p.instrument_id, p.trade_date): p for p in
                   session.query(DailyPrice).filter(DailyPrice.source == "amfi", DailyPrice.trade_date >= cutoff)}
        seen: set[str] = set()
        for r in rows:
            code = r.scheme_code
            if code in SAMPLE_SCHEME_CODES or code in seen:
                continue
            seen.add(code)
            name = r.scheme_name[:200]
            amc = (r.amc_name or "Unknown")[:100]
            fund = funds.get(code)
            if fund is None:
                fund = MutualFund(scheme_code=code, fund_name=name, amc=amc, category=r.category)
                session.add(fund)
                funds[code] = fund
                counts["funds_inserted"] += 1
            else:
                counts["funds_updated"] += 1
            fund.scheme_name, fund.fund_name = name, name
            fund.amc_name, fund.amc = amc, amc
            fund.category, fund.sub_category = r.category, r.sub_category
            fund.scheme_type = r.scheme_type
            fund.is_direct_plan, fund.is_growth_plan = r.is_direct_plan, r.is_growth_plan
            fund.nav, fund.nav_date = r.nav, r.nav_date.isoformat()
            fund.nav_source, fund.is_active = "amfi", True
            inst = instruments.upsert_mf(session, scheme_code=code, name=name, isin=r.isin_growth,
                                         isin_alt=r.isin_reinvest, seen_on=today, existing=insts)
            wants_history = (r.scheme_type == "open" and (r.is_growth_plan or bool(fund.track_nav))
                             and r.nav_date >= cutoff)
            if not wants_history:
                continue
            close = Decimal(str(r.nav))
            existing = history.get((inst.id, r.nav_date))
            if existing is None:
                point = DailyPrice(instrument_id=inst.id, trade_date=r.nav_date, close=close, source="amfi",
                                   ingested_at=now)
                session.add(point)
                history[(inst.id, r.nav_date)] = point
                counts["history_rows"] += 1
            elif Decimal(str(existing.close)) != close:
                existing.close = close
                existing.ingested_at = now
        for code, fund in funds.items():
            if fund.nav_source == "amfi" and code not in seen and code not in SAMPLE_SCHEME_CODES and fund.is_active:
                fund.is_active = False
                counts["deactivated"] += 1
                inst = insts.get(code)
                if inst is not None:
                    inst.status = "inactive"
        session.commit()
    logger.info("AMFI harvest: %s", counts)
    return counts
