"""FAKE-06 / GH-696: catalog GET endpoints never seed mock rows.

Illustrative mutual-fund, IPO, loan-offer and FD catalogs are seeded only at
startup and only with DEMO_MODE=true; forum boards are structural and always
seeded at startup, but never with a thread attributed to a real user.
"""
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import config.settings
from core import lifecycle
from database import get_session
from models.db_models import (
    Base,
    FixedDepositScheme,
    ForumBoard,
    ForumPost,
    ForumThread,
    IPOListing,
    LoanOffer,
    MutualFund,
    User,
)
from services import (
    fixed_deposit_service,
    forum_service,
    ipo_service,
    loan_marketplace_service,
    mutual_fund_service,
)

_MODELS = (MutualFund, IPOListing, ForumBoard, LoanOffer, FixedDepositScheme)
_GETS = (
    "/api/mutual-funds/",
    "/api/ipo",
    "/api/ipo/calendar",
    "/api/forum/boards",
    "/api/finance/loan-offers",
    "/api/fixed-deposits/schemes",
)


def _counts() -> dict:
    with get_session() as session:
        return {m.__name__: session.query(m).count() for m in _MODELS}


def test_get_does_not_seed(client, monkeypatch):
    # Startup seeding already ran when the session client started; DEMO_MODE
    # is switched on here only so the demo-gated loan/FD routes (FAKE-23)
    # reach their handlers, which must not seed on GET.
    monkeypatch.setattr(config.settings, "DEMO_MODE", True)
    before = _counts()
    for path in _GETS:
        assert client.get(path).status_code == 200, path
    assert _counts() == before


@pytest.mark.parametrize("demo_mode, expected", [
    (False, {"forum"}),
    (True, {"forum", "funds", "ipos", "loans", "fds"}),
])
def test_startup_seeding_gated_by_demo_mode(monkeypatch, demo_mode, expected):
    called = set()
    for module, attr, tag in (
        (forum_service, "seed_mock_boards_if_empty", "forum"),
        (mutual_fund_service, "seed_mock_funds_if_empty", "funds"),
        (ipo_service, "seed_mock_ipos_if_empty", "ipos"),
        (loan_marketplace_service, "seed_mock_loan_offers_if_empty", "loans"),
        (fixed_deposit_service, "seed_mock_fd_schemes_if_empty", "fds"),
    ):
        def _fake(tag=tag):
            called.add(tag)
            return 0
        _fake.__name__ = attr
        monkeypatch.setattr(module, attr, _fake)
    monkeypatch.setattr(config.settings, "DEMO_MODE", demo_mode)

    lifecycle._seed_catalogs()

    assert called == expected


def test_forum_seed_attributes_nothing_to_real_users(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    @contextmanager
    def _get_session():
        yield session

    monkeypatch.setattr(forum_service, "get_session", _get_session)
    session.add(User(username="first_real_user", password_hash="x", display_name="First"))
    session.commit()

    assert forum_service.seed_mock_boards_if_empty() == len(forum_service._MOCK_BOARDS)
    assert session.query(ForumThread).count() == 0
    assert session.query(ForumPost).count() == 0
    session.close()
