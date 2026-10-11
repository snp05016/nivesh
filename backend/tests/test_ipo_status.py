"""CMON-17: IPO status is derived from dates, not frozen seed values."""
from contextlib import contextmanager
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base, IPOListing
from services import ipo_service
from services.ipo_service import derive_ipo_status

OPEN, CLOSE, LIST = "2026-06-28", "2026-07-02", "2026-07-07"


@pytest.mark.parametrize(
    "today, expected",
    [
        (date(2026, 6, 27), "upcoming"),
        (date(2026, 6, 28), "open"),
        (date(2026, 7, 2), "open"),
        (date(2026, 7, 3), "closed"),
        (date(2026, 7, 7), "listed"),
        (date(2026, 10, 8), "listed"),
    ],
)
def test_derive_ipo_status(today, expected):
    assert derive_ipo_status(OPEN, CLOSE, LIST, today) == expected


def test_derive_ipo_status_edges():
    assert derive_ipo_status(None, CLOSE, LIST, date(2026, 10, 8)) is None
    # closed with no listing date yet stays closed
    assert derive_ipo_status(OPEN, CLOSE, None, date(2026, 10, 8)) == "closed"


@pytest.fixture()
def db_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    @contextmanager
    def _get_session():
        yield session

    monkeypatch.setattr(ipo_service, "get_session", _get_session)
    monkeypatch.setattr(ipo_service, "_today", lambda: date(2026, 10, 8))
    yield session
    session.close()


def test_list_filters_on_derived_status(db_session):
    db_session.add(IPOListing(
        company_name="Sunrise Logistics Ltd", symbol="SUNLOG",
        open_date=OPEN, close_date=CLOSE, listing_date=LIST,
        status="open", subscription_status="open",
    ))
    db_session.commit()

    assert ipo_service.list_ipos("open") == []
    listed = ipo_service.list_ipos("listed")
    assert [r.symbol for r in listed] == ["SUNLOG"]
    assert listed[0].subscription_status == "listed"
    assert ipo_service.get_ipo_by_symbol("sunlog").status == "listed"


def test_seed_rows_flagged_as_sample(db_session):
    from routers.ipo import IPOResponse

    ipo_service.seed_mock_ipos_if_empty()
    rows = ipo_service.list_ipos()
    assert rows and all(IPOResponse.model_validate(r).is_sample for r in rows)
    real = IPOListing(id=999, company_name="Real Co", symbol="REALCO")
    assert IPOResponse.model_validate(real).is_sample is False
