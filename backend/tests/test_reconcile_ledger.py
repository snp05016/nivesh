"""Money C4: scripts/reconcile_ledger.py reports the five discrepancy kinds and,
with --apply, fixes them so a second run reports none.

Hermetic: in-memory SQLite (database.get_session is redirected to it), no network.
"""
from __future__ import annotations

import csv
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# conftest.py patches heavy modules before any app import — rely on that here.
from models.db_models import Base, Portfolio, Transaction
from scripts import reconcile_ledger
from services.ledger_service import _holdings_row, record_transaction

UTC = timezone.utc
BOUGHT = datetime(2026, 1, 5, tzinfo=UTC)
EX_DATE = datetime(2026, 2, 1, 18, 29, 59, tzinfo=UTC)
AUTO_NOTE = "auto: corporate action ex 2026-02-02 (yfinance)"


def _f(v) -> float:  # type: ignore[misc]
    return float(v)  # type: ignore[arg-type]


@pytest.fixture()
def db_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    @contextmanager
    def mock_get_session():
        session = Session()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr("database.get_session", mock_get_session)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _row(session, user_id, ticker, shares, price):
    session.add(Portfolio(
        user_id=user_id, ticker=ticker, company_name=f"{ticker} Ltd", shares=shares,
        buy_price=price, group_name="holdings",
    ))


def _tx(session, user_id, ticker, tx_type, qty, price, date=BOUGHT, notes=None):
    session.add(Transaction(
        user_id=user_id, ticker=ticker, transaction_type=tx_type, quantity=qty, price=price,
        fees=0.0, date=date, notes=notes,
    ))


def _seed(session) -> None:
    _row(session, 1, "ROWONLY", 10.0, 100.0)                       # row_without_ledger
    _tx(session, 1, "GHOST", "BUY", 5.0, 50.0)                     # ledger_without_row
    _tx(session, 1, "QTY", "BUY", 10.0, 100.0)                     # quantity_mismatch
    _row(session, 1, "QTY", 12.0, 100.0)
    _tx(session, 1, "COST", "BUY", 10.0, 100.0)                    # cost_mismatch
    _row(session, 1, "COST", 10.0, 105.0)
    _tx(session, 1, "SPLITX", "BUY", 10.0, 100.0)                  # duplicate_auto_split
    _tx(session, 1, "SPLITX", "SPLIT", 2.0, 0.0, date=EX_DATE, notes=AUTO_NOTE)
    _tx(session, 1, "SPLITX", "SPLIT", 2.0, 0.0, date=EX_DATE, notes=AUTO_NOTE)
    _row(session, 1, "SPLITX", 40.0, 25.0)                         # the split applied twice
    _tx(session, 1, "FINE", "BUY", 3.0, 10.0)                      # consistent
    _row(session, 1, "FINE", 3.0, 10.0)
    _row(session, 2, "OTHER", 1.0, 10.0)                           # another user's row_without_ledger
    session.commit()


def _run(tmp_path, name, *args) -> list[dict]:
    out = tmp_path / f"{name}.csv"
    assert reconcile_ledger.main([*args, "--out", str(out)]) == 0
    with open(out, newline="") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == reconcile_ledger.FIELDS
        return list(reader)


def _kinds(rows) -> dict:
    return {(int(r["user_id"]), r["ticker"]): r["kind"] for r in rows}


def _holding(session, user_id, ticker):
    return _holdings_row(session, user_id, ticker)


def test_report_lists_the_five_kinds_and_changes_nothing(db_session, tmp_path):
    _seed(db_session)
    before = db_session.query(Transaction).count()

    rows = _run(tmp_path, "report", "--user-id", "1")

    assert _kinds(rows) == {
        (1, "ROWONLY"): "row_without_ledger",
        (1, "GHOST"): "ledger_without_row",
        (1, "QTY"): "quantity_mismatch",
        (1, "COST"): "cost_mismatch",
        (1, "SPLITX"): "duplicate_auto_split",
    }
    split = next(r for r in rows if r["ticker"] == "SPLITX")
    assert (float(split["read_shares"]), float(split["ledger_shares"]), float(split["ledger_avg_cost"])) == (40.0, 20.0, 50.0)
    db_session.expire_all()
    assert db_session.query(Transaction).count() == before
    assert (1, "OTHER") not in _kinds(rows)
    assert (2, "OTHER") in _kinds(_run(tmp_path, "all"))


def test_apply_fixes_everything_and_a_second_run_is_clean(db_session, tmp_path):
    _seed(db_session)

    applied = _run(tmp_path, "apply", "--user-id", "1", "--apply")
    assert len(applied) == 5
    assert _run(tmp_path, "again", "--user-id", "1") == []

    db_session.expire_all()
    shown = {t: _holding(db_session, 1, t) for t in ("ROWONLY", "GHOST", "QTY", "COST", "SPLITX")}
    assert shown["GHOST"] is None
    assert (_f(shown["QTY"].shares), _f(shown["QTY"].buy_price)) == (12.0, 100.0)  # type: ignore[union-attr]
    assert (_f(shown["COST"].shares), _f(shown["COST"].buy_price)) == (10.0, 105.0)  # type: ignore[union-attr]
    assert (_f(shown["SPLITX"].shares), _f(shown["SPLITX"].buy_price)) == (20.0, 50.0)  # type: ignore[union-attr]
    assert (_f(shown["ROWONLY"].shares), _f(shown["ROWONLY"].buy_price)) == (10.0, 100.0)  # type: ignore[union-attr]

    restated = db_session.query(Transaction).filter_by(notes=reconcile_ledger.RESTATE_NOTE).all()
    assert sorted(str(t.ticker) for t in restated) == ["COST", "GHOST", "QTY"]
    assert all(t.transaction_type == "ADJUST" for t in restated)
    opening = db_session.query(Transaction).filter_by(user_id=1, ticker="ROWONLY").one()
    assert opening.transaction_type == "BUY"
    # SPLITX was only recomputed: no ledger row added.
    assert db_session.query(Transaction).filter_by(ticker="SPLITX").count() == 3


def test_closed_ledger_without_row_is_not_resurrected(db_session, tmp_path):
    _seed(db_session)
    _run(tmp_path, "apply", "--user-id", "1", "--apply")

    db_session.expire_all()
    record_transaction(
        user_id=1, ticker="GHOST", transaction_type="BUY", quantity=1.0, price=60.0,
        company_name="GHOST Ltd", session=db_session,
    )
    row = _holding(db_session, 1, "GHOST")
    assert row is not None
    assert (_f(row.shares), _f(row.buy_price)) == (1.0, 60.0)  # not 6 shares: the old 5 stay closed
