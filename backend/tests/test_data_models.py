"""Data-foundation models: constraints, cascades and the erasure mapping (in-memory SQLite)."""
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.db_models import (
    Base, CorporateAction, CorporateActionApplication, DailyPrice, Instrument, PortfolioGroup, User,
)
from services.compliance_service import ERASURE_POLICY

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


@pytest.fixture
def session():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _eq(session, symbol="RELIANCE", **kw):
    inst = Instrument(asset_class="EQ", symbol=symbol, name=symbol, source="nse_equity_l", **kw)
    session.add(inst)
    session.flush()
    return inst


def _price(inst_id, d=date(2026, 10, 9), close=100, **kw):
    return DailyPrice(instrument_id=inst_id, trade_date=d, close=close, source="nse_bhavcopy",
                      ingested_at=NOW, **kw)


def test_duplicate_instrument_date_rejected(session):
    inst = _eq(session)
    session.add(_price(inst.id))
    session.commit()
    session.add(_price(inst.id))
    with pytest.raises(IntegrityError):
        session.commit()


def test_checks_reject_bad_values(session):
    inst = _eq(session)
    session.commit()
    session.add(Instrument(asset_class="XX", symbol="Z", name="Z", source="x"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    session.add(_price(inst.id, close=0))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    session.add(Instrument(asset_class="EQ", symbol="Y", name="Y", source="x", status="gone"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_two_mf_instruments_with_null_symbol(session):
    for code in ("100001", "100002"):
        session.add(Instrument(asset_class="MF", symbol=None, amfi_scheme_code=code, name=code, source="amfi"))
    session.commit()


def test_same_symbol_same_class_rejected(session):
    _eq(session, "TCS")
    session.commit()
    session.add(Instrument(asset_class="EQ", symbol="TCS", name="x", source="x"))
    with pytest.raises(IntegrityError):
        session.commit()


def _application_fixture(session):
    user = User(username="u1", password_hash="x", display_name="U")
    session.add(user)
    session.flush()
    groups = [PortfolioGroup(user_id=user.id, name=f"g{i}", is_default=(i == 1)) for i in (1, 2)]
    action = CorporateAction(ticker="ABC", ex_date="2026-10-09", purpose="Split", action_type="SPLIT_OR_BONUS",
                             ex_on=date(2026, 10, 9))
    session.add_all(groups + [action])
    session.flush()
    return user, groups, action


def _app(user, action, group_id):
    return CorporateActionApplication(user_id=user.id, corporate_action_id=action.id, group_id=group_id,
                                      status="pending", created_at=NOW)


def test_application_uniqueness_per_group(session):
    user, groups, action = _application_fixture(session)
    session.add_all([_app(user, action, groups[0].id), _app(user, action, groups[1].id)])
    session.commit()
    session.add_all([_app(user, action, None)])
    session.commit()
    session.add(_app(user, action, None))
    with pytest.raises(IntegrityError):
        session.commit()


def test_application_status_undone_rejected(session):
    user, groups, action = _application_fixture(session)
    app = _app(user, action, groups[0].id)
    app.status = "undone"
    session.add(app)
    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_instrument_cascades_to_prices(session):
    inst = _eq(session)
    session.add(_price(inst.id))
    session.commit()
    session.delete(inst)
    session.commit()
    assert session.query(DailyPrice).count() == 0


def test_erasure_policy_maps_applications():
    assert ERASURE_POLICY["corporate_action_applications.user_id"] == "delete"
