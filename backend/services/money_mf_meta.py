"""Mutual-fund metadata and NAV by ISIN (money cluster seam, spec 2.2).

The only module that knows the data cluster's schema: Instrument (asset_class
'MF', isin = growth/payout, isin_alt = reinvestment, amfi_scheme_code) joined to
MutualFund (scheme_code, scheme_name, amc_name, category, sub_category,
is_direct_plan, nav, nav_date). Until those land, scheme_info() returns {} and
funds are unpriced with unknown categories.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Iterable, Optional

from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SchemeInfo:
    isin: str
    amfi_code: Optional[str]
    name: Optional[str]
    amc: Optional[str]
    category: Optional[str]
    sub_category: Optional[str]
    is_direct: Optional[bool]
    nav: Optional[float]
    nav_date: Optional[date]


def _parse_nav_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def scheme_info(isins: Iterable[str]) -> dict[str, SchemeInfo]:
    """{isin: SchemeInfo} for the ISINs found (growth or reinvestment ISIN); {} when the
    data cluster's tables are absent or the query fails."""
    wanted = {str(i).strip().upper() for i in isins if i}
    if not wanted:
        return {}
    try:
        import models.db_models as db_models
        from database import get_session
        from sqlalchemy import or_

        Instrument = getattr(db_models, "Instrument")
        MutualFund = db_models.MutualFund
        with get_session() as session:
            rows = (
                session.query(Instrument, MutualFund)
                .join(MutualFund, MutualFund.scheme_code == Instrument.amfi_scheme_code)
                .filter(
                    Instrument.asset_class == "MF",
                    or_(Instrument.isin.in_(wanted), Instrument.isin_alt.in_(wanted)),
                )
                .all()
            )
            found: list[tuple[list[str], SchemeInfo]] = []
            for inst, mf in rows:
                keys = [k for k in (inst.isin, inst.isin_alt) if k in wanted]
                nav = float(mf.nav) if mf.nav is not None and float(mf.nav) > 0 else None
                found.append((keys, SchemeInfo(
                    isin=keys[0] if keys else "",
                    amfi_code=str(inst.amfi_scheme_code) if inst.amfi_scheme_code is not None else None,
                    name=mf.scheme_name or mf.fund_name or getattr(inst, "name", None),
                    amc=mf.amc_name or mf.amc,
                    category=mf.category,
                    sub_category=mf.sub_category,
                    is_direct=mf.is_direct_plan,
                    nav=nav,
                    nav_date=_parse_nav_date(mf.nav_date),
                )))
    except (ImportError, AttributeError, SQLAlchemyError) as e:
        logger.info("[money_mf_meta] scheme metadata unavailable: %s", type(e).__name__)
        return {}
    return {key: replace(info, isin=key) for keys, info in found for key in keys}
