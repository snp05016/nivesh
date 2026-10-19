"""Indian capital-gains rules for listed equity shares, versioned in code (I29, spec 3.7).

Pure: no DB, no network. Money is Decimal. These are informational working rules, not tax advice;
the methodology is in docs/money/TAX_METHODOLOGY.md and needs a chartered accountant's sign-off
before the report flag is enabled.
"""
from __future__ import annotations

import calendar
import re
from datetime import date
from decimal import Decimal
from typing import Optional

from core.timeutil import ist_today

RULES_VERSION = "in-cg-2026.1"
FA2024_CUTOFF = date(2024, 7, 23)       # rates changed for sales on or after this date
GRANDFATHER_LAST_ACQ = date(2018, 1, 31)  # shares acquired on or before this date get the FMV floor
NEW_ACT_START = date(2026, 4, 1)        # sections 111A/112A become 196/198
FIRST_FY_START_YEAR = 2018

STCG, LTCG = "STCG", "LTCG"

_FY_RE = re.compile(r"^(\d{4})-(\d{2})$")
_EXEMPTION_OLD = Decimal("100000")
_EXEMPTION_NEW = Decimal("125000")
_RATES = {
    (STCG, "pre_2024_07_23"): Decimal("15"),
    (STCG, "post_2024_07_23"): Decimal("20"),
    (LTCG, "pre_2024_07_23"): Decimal("10"),
    (LTCG, "post_2024_07_23"): Decimal("12.5"),
}


def fy_label(start_year: int) -> str:
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def current_fy(today: Optional[date] = None) -> str:
    """The Indian financial year (April to March) containing `today` (IST)."""
    today = today or ist_today()
    return fy_label(today.year if today.month >= 4 else today.year - 1)


def fy_bounds(fy: str, today: Optional[date] = None) -> tuple[date, date]:
    """(first day, last day) of financial year `fy` ('2025-26'). ValueError unless the label is
    well formed, consecutive, from 2018-19 up to the current FY."""
    m = _FY_RE.match(fy or "")
    if not m:
        raise ValueError("FY must look like 2025-26")
    start_year = int(m.group(1))
    if int(m.group(2)) != (start_year + 1) % 100:
        raise ValueError("FY years must be consecutive")
    current_start = int(current_fy(today).split("-")[0])
    if not FIRST_FY_START_YEAR <= start_year <= current_start:
        raise ValueError("FY out of range")
    return date(start_year, 4, 1), date(start_year + 1, 3, 31)


def fy_of(d: date) -> str:
    return fy_label(d.year if d.month >= 4 else d.year - 1)


def add_months(d: date, months: int) -> date:
    """`d` plus whole calendar months, clamped to the month end (31 Jan + 1 month = 28/29 Feb)."""
    index = d.year * 12 + (d.month - 1) + months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def is_long_term(acquired: date, sold: date) -> bool:
    """Listed shares are long-term when sold more than 12 calendar months after acquisition."""
    return sold > add_months(acquired, 12)


def rate_period(sold: date) -> str:
    return "pre_2024_07_23" if sold < FA2024_CUTOFF else "post_2024_07_23"


def rate_pct(term: str, sold: date) -> Decimal:
    return _RATES[(term, rate_period(sold))]


def section(term: str, sold: date) -> str:
    new = sold >= NEW_ACT_START
    if term == STCG:
        return "196" if new else "111A"
    return "198" if new else "112A"


def ltcg_exemption(fy: str) -> Decimal:
    """Rs 1,00,000 up to FY 2023-24, Rs 1,25,000 from FY 2024-25."""
    start_year = int(fy.split("-")[0])
    return _EXEMPTION_OLD if start_year <= 2023 else _EXEMPTION_NEW


def grandfathered_cost(actual: Decimal, fmv_total: Decimal, sale: Decimal) -> Decimal:
    """Cost of acquisition for shares bought on or before 31-Jan-2018: the higher of the actual
    cost and the lower of the 31-Jan-2018 fair market value and the sale value."""
    return max(actual, min(fmv_total, sale))
