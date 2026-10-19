"""Regular-plan cost data for the X-ray (I34, spec 3.6).

The expense ratios come from an owner-maintained CSV (data/mf_ter_large_amcs.csv, shipped
header-only; AMFI publishes no bulk file). Rows are validated, the newest ``as_of`` must be at most
45 days old, and nothing here recommends a plan or a switch: it states published figures.
"""
from __future__ import annotations

import csv
import functools
import logging
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

from core.timeutil import ist_today

logger = logging.getLogger(__name__)

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "mf_ter_large_amcs.csv"
STALE_AFTER_DAYS = 45
SOURCE = "AMC expense-ratio disclosures"
SOURCE_URL = "https://www.amfiindia.com/ter-of-mf-schemes"
_ISIN_RE = re.compile(r"^INF[A-Z0-9]{9}$")
_TWO = Decimal("0.01")


def _row(raw: dict[str, str], today: date) -> Optional[dict[str, Any]]:
    try:
        regular_isin = (raw.get("regular_isin") or "").strip().upper()
        direct_isin = (raw.get("direct_isin") or "").strip().upper()
        if not _ISIN_RE.match(regular_isin) or not _ISIN_RE.match(direct_isin):
            return None
        regular = Decimal((raw.get("regular_ter_pct") or "").strip())
        direct = Decimal((raw.get("direct_ter_pct") or "").strip())
        if not (0 < regular <= 3 and 0 < direct <= 3 and direct <= regular):
            return None
        as_of = datetime.strptime((raw.get("as_of") or "").strip(), "%Y-%m-%d").date()
        if as_of > today:
            return None
    except (InvalidOperation, ValueError):
        return None
    return {"regular_isin": regular_isin, "direct_isin": direct_isin, "scheme_name": (raw.get("scheme_name") or "").strip(),
            "amc": (raw.get("amc") or "").strip(), "regular": regular, "direct": direct, "as_of": as_of,
            "source_url": (raw.get("source_url") or "").strip()}


@functools.lru_cache(maxsize=4)
def load_rows(path: str = str(CSV_PATH)) -> tuple[dict[str, Any], ...]:
    """Valid rows of the TER file, read once per process. Bad rows are logged and skipped."""
    today = ist_today()
    rows: list[dict[str, Any]] = []
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            for number, raw in enumerate(csv.DictReader(fh), start=2):
                parsed = _row(raw, today)
                if parsed is None:
                    logger.warning("[money_commission] skipped invalid TER row %d", number)
                else:
                    rows.append(parsed)
    except OSError as exc:
        logger.warning("[money_commission] TER file unreadable: %s", type(exc).__name__)
    return tuple(rows)


def _money(value: Decimal) -> float:
    return float(value.quantize(_TWO))


def commission_drag(
    funds: list[dict[str, Any]], *, path: Optional[str] = None, today: Optional[date] = None
) -> dict[str, Any]:
    """The X-ray's ``commission_drag`` block for ``funds`` (isin, name, value_inr, is_direct)."""
    today = today or ist_today()
    rows = load_rows(path or str(CSV_PATH))
    if not rows:
        return {"available": False, "reason": "ter_data_missing"}
    newest = max(r["as_of"] for r in rows)
    if today - newest > timedelta(days=STALE_AFTER_DAYS):
        return {"available": False, "reason": "ter_data_stale"}

    by_regular = {r["regular_isin"]: r for r in rows}
    covered: list[dict[str, Any]] = []
    uncovered = 0
    for fund in funds:
        if fund.get("is_direct") is not False:
            continue  # direct or unknown plans carry no commission to compare
        row = by_regular.get(str(fund["isin"]).upper())
        if row is None:
            uncovered += 1
            continue
        value = Decimal(str(fund["value_inr"]))
        gap = row["regular"] - row["direct"]
        covered.append({
            "isin": row["regular_isin"], "name": fund.get("name") or row["scheme_name"], "value_inr": _money(value),
            "regular_ter_pct": float(row["regular"]), "direct_ter_pct": float(row["direct"]),
            "gap_pp": _money(gap), "annual_cost_inr": _money(value * gap / 100),
        })
    if not covered:
        return {"available": False, "reason": "no_regular_funds"}
    total = sum((Decimal(str(f["annual_cost_inr"])) for f in covered), Decimal(0))
    return {
        "available": True, "as_of": newest.isoformat(), "total_annual_cost_inr": _money(total),
        "uncovered_regular_funds": uncovered, "funds": covered, "source": SOURCE, "source_url": SOURCE_URL,
    }
