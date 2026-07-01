"""IPO Hub service — business logic + repository access for IPOListing.

Controller-Service-Repository: routers/ipo.py must only validate HTTP input
and call functions here. All session.query() calls for IPOListing live in
this module.
"""
from typing import Optional

from database import get_session
from models.db_models import IPOListing

VALID_STATUSES = {"upcoming", "open", "closed", "listed"}


# ---------------------------------------------------------------------------
# Mock/seed data — no live scraper is wired in for this pass. This mirrors
# the shape a real NSE/BSE IPO harvester would eventually populate.
# Clearly marked MOCK DATA; safe to delete once a real harvester exists.
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
        "gmp": 45.0,
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
        "gmp": 12.0,
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
        "gmp": 95.0,
    },
]


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
                gmp=row["gmp"],
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
        query = session.query(IPOListing)
        if status:
            query = query.filter(IPOListing.status == status)
        return query.order_by(IPOListing.open_date.desc()).all()


def get_ipo_by_id(ipo_id: int) -> Optional[IPOListing]:
    with get_session() as session:
        return session.query(IPOListing).filter(IPOListing.id == ipo_id).first()


def get_ipo_by_symbol(symbol: str) -> Optional[IPOListing]:
    with get_session() as session:
        return (
            session.query(IPOListing)
            .filter(IPOListing.symbol == symbol.upper())
            .first()
        )


def get_subscription_status(ipo_id: int) -> Optional[IPOListing]:
    """Return the IPO row containing subscription (QIB/NII/Retail) figures."""
    return get_ipo_by_id(ipo_id)
