"""
Nivesh AMFI NAV Harvester — daily Mutual Fund NAV fetcher.

Fetches the public plain-text NAV file published by AMFI (Association of
Mutual Funds in India) at https://www.amfiindia.com/spages/NAVAll.txt and
upserts the latest NAV / NAV date onto existing `MutualFund` rows.

Scope note: this harvester does NOT create fund metadata rows. The
`MutualFund` model (and its seeding) is owned by the Backend MF Router
Agent — this harvester only refreshes `nav` / `nav_date` / `scheme_name`
for schemes that are already seeded in the DB, matched on `scheme_code`.
Unknown scheme codes are skipped (counted, not created).

Public API:
    harvest_navs()  — fetch + parse + upsert. Returns a summary dict.
    fetch_amfi_nav_text()   — raw text fetch (network I/O only).
    parse_amfi_nav_text()   — pure parsing, no I/O, easy to unit test.

Standalone usage:
    python -m services.amfi_nav_harvester
    (run from backend/, or `python backend/services/amfi_nav_harvester.py`)

Scheduling: intended to be triggered once daily, shortly after AMFI
publishes the file (~9-11 PM IST on business days), e.g. via APScheduler
(see backend/services/harvester_service.py for the existing scheduler
pattern) or a nightly CRON entry calling `harvest_navs()`.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional

import requests

# Allow `python backend/services/amfi_nav_harvester.py` to work by ensuring
# backend/ is on sys.path (mirrors the pattern used by other standalone
# harvester scripts in this repo).
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

logger = logging.getLogger("amfi_nav_harvester")

AMFI_NAV_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
_REQUEST_TIMEOUT_SECS = 30


@dataclass
class NavRecord:
    """One parsed line from AMFI's NAVAll.txt."""
    scheme_code: str
    isin_div_payout: str
    isin_div_reinvestment: str
    scheme_name: str
    nav: float
    nav_date: date


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_amfi_nav_text(url: str = AMFI_NAV_URL) -> str:
    """Fetch the raw semicolon-delimited NAV file text from AMFI.

    Raises:
        requests.RequestException: on network / HTTP failure.
    """
    response = requests.get(url, timeout=_REQUEST_TIMEOUT_SECS)
    response.raise_for_status()
    return response.text


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------

def _parse_nav_date(raw: str) -> Optional[date]:
    """AMFI dates are formatted like '02-Jul-2026'."""
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%d-%b-%Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def parse_amfi_nav_text(raw_text: str) -> List[NavRecord]:
    """Parse AMFI's NAVAll.txt into a list of NavRecord.

    Format (semicolon-delimited):
        Scheme Code;ISIN Div Payout;ISIN Div Reinvestment;Scheme Name;NAV;Date

    Category header lines (no semicolons, e.g. "Open Ended Schemes(Debt)")
    and the repeated column-header row are skipped. Malformed / incomplete
    rows are skipped and logged.
    """
    records: List[NavRecord] = []
    skipped = 0

    for line in raw_text.splitlines():
        line = line.strip()
        if not line or ";" not in line:
            continue  # blank line or category header, e.g. "Open Ended Schemes(Debt)"

        parts = [p.strip() for p in line.split(";")]
        if parts[0] in ("Scheme Code", ""):
            continue  # repeated column header or malformed lead field

        if len(parts) < 6:
            skipped += 1
            continue

        scheme_code, isin_payout, isin_reinvest, scheme_name, nav_str, date_str = parts[:6]

        if not scheme_code or nav_str.upper() == "N.A." or not nav_str:
            skipped += 1
            continue

        try:
            nav_value = float(nav_str)
        except ValueError:
            skipped += 1
            continue

        nav_date = _parse_nav_date(date_str)
        if nav_date is None:
            skipped += 1
            continue

        records.append(
            NavRecord(
                scheme_code=scheme_code,
                isin_div_payout=isin_payout,
                isin_div_reinvestment=isin_reinvest,
                scheme_name=scheme_name,
                nav=nav_value,
                nav_date=nav_date,
            )
        )

    if skipped:
        logger.info(f"[amfi_nav_harvester] Skipped {skipped} malformed/NA rows during parse")

    return records


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

def _upsert_navs(records: List[NavRecord]) -> dict:
    """Update nav/nav_date (and scheme_name, if the column exists) on
    existing MutualFund rows, matched by scheme_code.

    Does NOT create new MutualFund rows — schemes not already seeded are
    skipped. This intentionally avoids owning MutualFund metadata, which
    belongs to the Backend MF Router Agent.
    """
    from database import get_session
    from models.db_models import MutualFund

    # scheme_code / nav_date are expected columns on MutualFund owned by the
    # MF Router Agent. Guard with hasattr so this harvester degrades
    # gracefully (skips instead of crashing) if that migration hasn't
    # landed yet in this checkout.
    has_scheme_code = hasattr(MutualFund, "scheme_code")
    has_nav_date = hasattr(MutualFund, "nav_date")
    has_scheme_name = hasattr(MutualFund, "scheme_name")

    if not has_scheme_code:
        logger.error(
            "[amfi_nav_harvester] MutualFund.scheme_code column not found — "
            "cannot match AMFI records to seeded funds. Skipping upsert. "
            "(Waiting on MF Router Agent's schema migration.)"
        )
        return {"updated": 0, "skipped": len(records), "not_found": len(records)}

    updated = 0
    not_found = 0

    with get_session() as session:
        # Pull matching rows in one query rather than N queries.
        wanted_codes = [r.scheme_code for r in records]
        existing = (
            session.query(MutualFund)
            .filter(MutualFund.scheme_code.in_(wanted_codes))
            .all()
        )
        by_code = {row.scheme_code: row for row in existing}

        for rec in records:
            row = by_code.get(rec.scheme_code)
            if row is None:
                not_found += 1
                continue

            row.nav = rec.nav
            if has_nav_date:
                row.nav_date = rec.nav_date
            if has_scheme_name:
                row.scheme_name = rec.scheme_name
            updated += 1

        session.commit()

    return {"updated": updated, "skipped": 0, "not_found": not_found}


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def harvest_navs(url: str = AMFI_NAV_URL) -> dict:
    """Fetch, parse, and upsert the latest AMFI NAV file.

    Returns a summary dict, e.g.:
        {"parsed": 12345, "updated": 40, "not_found": 12305, "error": None}

    Never raises — failures are logged and reflected in the "error" key so
    callers (CRON/APScheduler) can retry on the next scheduled run without
    crashing the process.
    """
    try:
        raw_text = fetch_amfi_nav_text(url)
    except Exception as e:
        logger.error(f"[amfi_nav_harvester] Failed to fetch AMFI NAV file: {e}")
        return {"parsed": 0, "updated": 0, "not_found": 0, "error": str(e)}

    records = parse_amfi_nav_text(raw_text)
    logger.info(f"[amfi_nav_harvester] Parsed {len(records)} NAV records from AMFI")

    if not records:
        return {"parsed": 0, "updated": 0, "not_found": 0, "error": "no records parsed"}

    try:
        result = _upsert_navs(records)
    except Exception as e:
        logger.error(f"[amfi_nav_harvester] Failed to upsert NAV records: {e}")
        return {"parsed": len(records), "updated": 0, "not_found": 0, "error": str(e)}

    summary = {
        "parsed": len(records),
        "updated": result["updated"],
        "not_found": result["not_found"],
        "error": None,
    }
    logger.info(
        f"[amfi_nav_harvester] Done — parsed={summary['parsed']} "
        f"updated={summary['updated']} not_found(unseeded)={summary['not_found']}"
    )
    return summary


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    outcome = harvest_navs()
    print(outcome)
