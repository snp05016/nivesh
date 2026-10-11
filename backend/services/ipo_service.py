"""IPO Hub service — business logic + repository access for IPOListing.

Controller-Service-Repository: routers/ipo.py must only validate HTTP input
and call functions here. All session.query() calls for IPOListing live in
this module.
"""
from datetime import date
from typing import Optional

from database import get_session
from models.db_models import IPOListing

VALID_STATUSES = {"upcoming", "open", "closed", "listed"}


# ---------------------------------------------------------------------------
# Mock/seed data — no live scraper is wired in for this pass. This mirrors
# the shape a real NSE/BSE IPO harvester would eventually populate.
# Clearly marked MOCK DATA; safe to delete once a real harvester exists.
# Seeded only at startup and only when DEMO_MODE=true (main._seed_catalogs);
# migration e0edc81fbf84 purges these rows from existing databases.
# ---------------------------------------------------------------------------
_MOCK_IPOS = [
    {
        "company_name": "Nova Fintech Ltd",
        "symbol": "NOVAFIN",
        "price_band_low": 410.0,
        "price_band_high": 432.0,
        "lot_size": 34,
        "issue_size_cr": 950.0,
        "open_date": "2026-07-08",
        "close_date": "2026-07-10",
        "listing_date": "2026-07-15",
        "status": "upcoming",
        "subscription_qib": None,
        "subscription_nii": None,
        "subscription_retail": None,
    },
    {
        "company_name": "Sunrise Logistics Ltd",
        "symbol": "SUNLOG",
        "price_band_low": 88.0,
        "price_band_high": 92.0,
        "lot_size": 160,
        "issue_size_cr": 320.5,
        "open_date": "2026-06-28",
        "close_date": "2026-07-02",
        "listing_date": "2026-07-07",
        "status": "open",
        "subscription_qib": 3.2,
        "subscription_nii": 5.8,
        "subscription_retail": 2.1,
    },
    {
        "company_name": "Bharat Precision Engineering Ltd",
        "symbol": "BPRECIS",
        "price_band_low": 610.0,
        "price_band_high": 640.0,
        "lot_size": 23,
        "issue_size_cr": 1250.0,
        "open_date": "2026-06-18",
        "close_date": "2026-06-20",
        "listing_date": "2026-06-25",
        "status": "closed",
        "subscription_qib": 18.4,
        "subscription_nii": 22.1,
        "subscription_retail": 9.6,
    },
]


# Fictional seed rows; the router flags these as is_sample so clients can label them.
SAMPLE_SYMBOLS = frozenset(r["symbol"] for r in _MOCK_IPOS)


def _today() -> date:
    return date.today()


def derive_ipo_status(
    open_date: Optional[str],
    close_date: Optional[str],
    listing_date: Optional[str],
    today: date,
) -> Optional[str]:
    """Status from ISO dates relative to today; None (keep stored) without an open date."""
    if not open_date:
        return None
    t = today.isoformat()  # ISO strings compare chronologically
    if t < open_date:
        return "upcoming"
    if not close_date or t <= close_date:
        return "open"
    if listing_date and t >= listing_date:
        return "listed"
    return "closed"


def _sync_statuses(session) -> None:
    """Persist date-derived statuses so the status filter sees current values."""
    today = _today()
    changed = False
    for row in session.query(IPOListing).all():
        derived = derive_ipo_status(row.open_date, row.close_date, row.listing_date, today)
        if derived and (row.status != derived or row.subscription_status != derived):
            row.status = derived
            row.subscription_status = derived
            changed = True
    if changed:
        session.commit()


def seed_mock_ipos_if_empty() -> int:
    """Populate ipo_listings with mock data when the table is empty.

    MOCK DATA — for development/demo only, no live scraping in this pass.
    Returns the number of rows inserted.
    """
    with get_session() as session:
        existing = session.query(IPOListing).count()
        if existing > 0:
            return 0
        inserted = 0
        for row in _MOCK_IPOS:
            ipo = IPOListing(
                company_name=row["company_name"],
                symbol=row["symbol"],
                price_band_low=row["price_band_low"],
                price_band_high=row["price_band_high"],
                # legacy mirror fields for backward compatibility
                issue_price_min=row["price_band_low"],
                issue_price_max=row["price_band_high"],
                lot_size=row["lot_size"],
                issue_size_cr=row["issue_size_cr"],
                open_date=row["open_date"],
                close_date=row["close_date"],
                listing_date=row["listing_date"],
                status=row["status"],
                subscription_status=row["status"],
                subscription_qib=row["subscription_qib"],
                subscription_nii=row["subscription_nii"],
                subscription_retail=row["subscription_retail"],
            )
            session.add(ipo)
            inserted += 1
        session.commit()
        return inserted


def list_ipos(status: Optional[str] = None) -> list[IPOListing]:
    """List IPOs, optionally filtered by status (upcoming/open/closed/listed)."""
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of {sorted(VALID_STATUSES)}")
    with get_session() as session:
        _sync_statuses(session)
        query = session.query(IPOListing)
        if status:
            query = query.filter(IPOListing.status == status)
        return query.order_by(IPOListing.open_date.desc()).all()


def get_ipo_by_id(ipo_id: int) -> Optional[IPOListing]:
    with get_session() as session:
        _sync_statuses(session)
        return session.query(IPOListing).filter(IPOListing.id == ipo_id).first()


def get_ipo_by_symbol(symbol: str) -> Optional[IPOListing]:
    with get_session() as session:
        _sync_statuses(session)
        return (
            session.query(IPOListing)
            .filter(IPOListing.symbol == symbol.upper())
            .first()
        )


def get_subscription_status(ipo_id: int) -> Optional[IPOListing]:
    """Return the IPO row containing subscription (QIB/NII/Retail) figures."""
    return get_ipo_by_id(ipo_id)
