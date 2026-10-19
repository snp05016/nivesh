"""Money C4: ledger asset_class, auto-split dedupe, ADJUST kinds and the CAS helpers.

- 300 seeded random sequences (BUY, SELL within the holding, ADJUST, SPLIT,
  BONUS; stocks and funds) written through record_transaction(session=...):
  the read model always equals an independent replay;
- two auto corporate-action SPLIT rows on one date apply once;
- adjust_kinds: noop / restate / close;
- restate_position is idempotent per key; remove_import_batch undoes a batch;
- the multi-asset POST is retired (410).

Hermetic: in-memory SQLite per test, no network.
"""
from __future__ import annotations

import math
import random
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# conftest.py patches heavy modules before any app import — rely on that here.
from models.db_models import Base, ImportBatch, Portfolio, PortfolioGroup, Transaction
from services.ledger_service import (
    LedgerError, _holdings_row, _ledger_rows, _replay, adjust_kinds, adjust_position, close_position,
    dedupe_auto_splits, is_opening_balance, record_transaction, remove_import_batch,
    restate_position,
)

SEED = 20261011
SEQUENCES = 300
UID = 1
UTC = timezone.utc


def _f(v) -> float:  # type: ignore[misc]
    return float(v)  # type: ignore[arg-type]


@pytest.fixture()
def db_session(monkeypatch):
    """In-memory SQLite; database.get_session is redirected to it for the
    service functions that open their own session (adjust_position, close_position)."""
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


def _holding(session, ticker: str) -> Optional[Portfolio]:
    # The ledger's own reader: it opts in to fund rows (include_mf).
    return _holdings_row(session, UID, ticker)


def _write(session, ticker, tx_type, qty, price, asset_class="EQ", date=None, notes=None, group_id=None):
    return record_transaction(
        user_id=UID, ticker=ticker, transaction_type=tx_type, quantity=qty, price=price,
        group_id=group_id, date=date, notes=notes, company_name="Test Co",
        session=session, asset_class=asset_class,
    )


# ---------------------------------------------------------------------------
# Property: read model == independent replay
# ---------------------------------------------------------------------------

def _reference(ops: list[tuple[str, float, float]]) -> tuple[float, float]:
    """The WAC rules written out independently of ledger_service (same float order)."""
    shares = cost = 0.0
    for kind, q, p in ops:
        if kind == "BUY":
            cost += q * p + 0.0
            shares += q
        elif kind == "SELL":
            if shares > 0:
                sold = min(q, shares)
                cost -= sold * (cost / shares)
                shares -= sold
        elif kind == "SPLIT":
            if q > 0 and shares > 0:
                shares *= q
        elif kind == "BONUS":
            shares += q
        elif kind == "ADJUST":
            shares = q
            cost = q * p
    shares = round(shares, 6)
    return shares, (round(cost / shares, 6) if shares > 0 else 0.0)


def _raw_shares(ops: list[tuple[str, float, float]]) -> float:
    shares = 0.0
    for kind, q, _p in ops:
        if kind == "BUY" or kind == "BONUS":
            shares += q
        elif kind == "SELL":
            shares -= min(q, shares) if shares > 0 else 0.0
        elif kind == "SPLIT" and q > 0 and shares > 0:
            shares *= q
        elif kind == "ADJUST":
            shares = q
    return shares


def _next_op(rng: random.Random, held: float) -> Optional[tuple[str, float, float]]:
    kind = rng.choice(["BUY", "BUY", "SELL", "SELL", "ADJUST", "SPLIT", "BONUS"])
    if kind == "BUY":
        return kind, max(round(rng.uniform(0.001, 100.0), 3), 0.001), round(rng.uniform(1.0, 5000.0), 2)
    if kind == "SELL":
        qty = math.floor(held * rng.random() * 1000) / 1000  # 3 dp, never above the holding
        return (kind, qty, round(rng.uniform(1.0, 5000.0), 2)) if held > 0.001 and qty > 0 else None
    if kind == "ADJUST":
        if rng.random() < 0.25:
            return kind, 0.0, 0.0
        return kind, max(round(rng.uniform(0.001, 100.0), 3), 0.001), round(rng.uniform(1.0, 5000.0), 2)
    if kind == "SPLIT":
        return kind, rng.choice([2.0, 3.0, 0.5]), 0.0
    bonus = round(held * rng.choice([0.5, 1.0]), 3)
    return (kind, bonus, 0.0) if held > 0.001 and bonus > 0 else None


def test_read_model_equals_replay_for_random_sequences(db_session):
    rng = random.Random(SEED)
    db_session.add(PortfolioGroup(user_id=UID, name="Core Holdings", is_default=True))
    db_session.commit()
    checked = 0
    for n in range(SEQUENCES):
        ticker = f"SEQ{n:03d}"
        asset_class = rng.choice(["EQ", "MF"])
        ops: list[tuple[str, float, float]] = []
        for _ in range(rng.randint(1, 10)):
            op = _next_op(rng, _raw_shares(ops))
            if op is None:
                continue
            _write(db_session, ticker, op[0], op[1], op[2], asset_class=asset_class)
            ops.append(op)

            want_shares, want_avg = _reference(ops)
            ledger_shares, ledger_avg = _replay(_ledger_rows(db_session, UID, ticker))
            row = _holding(db_session, ticker)
            assert abs(ledger_shares - want_shares) <= 1e-9 and abs(ledger_avg - want_avg) <= 1e-9, (ticker, ops)
            if want_shares <= 0:
                assert row is None, (ticker, ops)
            else:
                assert row is not None, (ticker, ops)
                assert abs(_f(row.shares) - want_shares) <= 1e-9, (ticker, ops)
                assert abs(_f(row.buy_price) - want_avg) <= 1e-9, (ticker, ops)
                assert str(row.asset_class) == asset_class
            checked += 1
        db_session.commit()
    assert checked > SEQUENCES  # the generator really produced sequences
    classes = {r[0] for r in db_session.query(Transaction.asset_class).distinct()}
    assert classes == {"EQ", "MF"}


def test_asset_class_is_validated(db_session):
    with pytest.raises(ValueError):
        _write(db_session, "BAD", "BUY", 1.0, 10.0, asset_class="GOLD")
    assert db_session.query(Transaction).count() == 0


# ---------------------------------------------------------------------------
# Auto-split dedupe and pure helpers
# ---------------------------------------------------------------------------

def test_two_auto_splits_on_one_date_apply_once(db_session):
    core = PortfolioGroup(user_id=UID, name="Core Holdings", is_default=True)
    other = PortfolioGroup(user_id=UID, name="Second", is_default=False)
    db_session.add_all([core, other])
    db_session.flush()
    bought = datetime(2026, 1, 5, tzinfo=UTC)
    ex = datetime(2026, 2, 1, 18, 29, 59, tzinfo=UTC)
    note = "auto: corporate action ex 2026-02-02 (yfinance)"
    _write(db_session, "DUP", "BUY", 10.0, 100.0, date=bought, group_id=core.id)
    _write(db_session, "DUP", "SPLIT", 2.0, 0.0, date=ex, notes=note, group_id=core.id)
    _write(db_session, "DUP", "SPLIT", 2.0, 0.0, date=ex, notes=note.upper(), group_id=other.id)

    row = _holding(db_session, "DUP")
    assert row is not None
    assert _f(row.shares) == 20.0
    assert _f(row.buy_price) == 50.0
    rows = _ledger_rows(db_session, UID, "DUP")
    assert len(rows) == 3 and len(dedupe_auto_splits(rows)) == 2


def test_manual_splits_are_not_deduplicated(db_session):
    when = datetime(2026, 3, 2, tzinfo=UTC)
    rows = [
        Transaction(id=1, ticker="X", transaction_type="SPLIT", quantity=2.0, price=0.0, date=when, notes=None),
        Transaction(id=2, ticker="X", transaction_type="SPLIT", quantity=2.0, price=0.0, date=when, notes="manual"),
    ]
    assert dedupe_auto_splits(rows) == rows


@pytest.mark.parametrize(
    "tx_type,notes,expected",
    [
        ("BUY", "Opening balance (pre-ledger holding)", True),
        ("BUY", "  legacy MIGRATION backfill", True),
        ("BUY", "Bought on dip", False),
        ("BUY", None, False),
        ("ADJUST", "Opening balance (pre-ledger holding)", False),
    ],
)
def test_is_opening_balance(tx_type, notes, expected):
    assert is_opening_balance(Transaction(transaction_type=tx_type, notes=notes)) is expected


def test_adjust_kinds_noop_restate_close(db_session):
    db_session.add(PortfolioGroup(user_id=UID, name="Core Holdings", is_default=True))
    db_session.flush()
    _write(db_session, "KND", "BUY", 10.0, 100.0)
    db_session.commit()

    assert adjust_position(UID, "KND", 10.0, 100.0, target_price=150.0) is not None  # target-only edit
    assert adjust_position(UID, "KND", 12.0, 95.0) is not None
    assert close_position(UID, "KND") is True

    db_session.expire_all()
    rows = _ledger_rows(db_session, UID, "KND")
    kinds = adjust_kinds(rows)
    adjust_ids = [int(t.id) for t in rows if t.transaction_type == "ADJUST"]  # type: ignore[arg-type]
    assert [kinds[i] for i in adjust_ids] == ["noop", "restate", "close"]
    assert set(kinds) == set(adjust_ids)


# ---------------------------------------------------------------------------
# CAS helpers
# ---------------------------------------------------------------------------

def _batch(session) -> int:
    batch = ImportBatch(user_id=UID, status="previewed", file_sha256="ab" * 32)
    session.add(batch)
    session.flush()
    return int(batch.id)  # type: ignore[arg-type]


ISIN = "INF179K01VC4"


def test_restate_position_is_idempotent_per_key(db_session):
    batch_id = _batch(db_session)
    key = "casbal:" + "a" * 48
    when = datetime(2026, 10, 8, tzinfo=UTC)
    first = restate_position(
        db_session, UID, ISIN, 10.0, 50.0, date=when, notes="CAS balance", asset_class="MF",
        import_batch_id=batch_id, client_request_id=key, company_name="HDFC Flexi Cap Fund",
    )
    again = restate_position(
        db_session, UID, ISIN, 11.0, 51.0, date=when, notes="CAS balance", asset_class="MF",
        import_batch_id=batch_id, client_request_id=key,
    )
    assert first is not None and again is None
    assert db_session.query(Transaction).filter_by(user_id=UID, client_request_id=key).count() == 1
    assert str(first.transaction_type) == "ADJUST"
    assert first.import_batch_id is not None and int(first.import_batch_id) == batch_id  # type: ignore[arg-type]
    row = _holding(db_session, ISIN)
    assert row is not None
    assert (_f(row.shares), _f(row.buy_price), str(row.asset_class)) == (10.0, 50.0, "MF")


def test_remove_import_batch_restores_previous_position(db_session):
    first_batch, second_batch = _batch(db_session), _batch(db_session)
    restate_position(
        db_session, UID, ISIN, 10.0, 50.0, date=datetime(2026, 3, 31, tzinfo=UTC), asset_class="MF",
        import_batch_id=first_batch, client_request_id="casbal:first",
    )
    restate_position(
        db_session, UID, ISIN, 15.0, 52.0, date=datetime(2026, 9, 30, tzinfo=UTC), asset_class="MF",
        import_batch_id=second_batch, client_request_id="casbal:second",
    )
    row = _holding(db_session, ISIN)
    assert row is not None and _f(row.shares) == 15.0

    assert remove_import_batch(db_session, UID, second_batch) == 1
    row = _holding(db_session, ISIN)
    assert row is not None
    assert (_f(row.shares), _f(row.buy_price)) == (10.0, 50.0)

    assert remove_import_batch(db_session, UID, first_batch) == 1
    assert _holding(db_session, ISIN) is None
    assert db_session.query(Transaction).filter_by(user_id=UID, ticker=ISIN).count() == 0
    assert remove_import_batch(db_session, UID, first_batch) == 0


def test_remove_import_batch_keeps_manual_rows_and_restores_them(db_session):
    _write(db_session, "UNDO", "BUY", 5.0, 100.0, date=datetime(2026, 1, 5, tzinfo=UTC))
    batch_id = _batch(db_session)
    restate_position(
        db_session, UID, "UNDO", 8.0, 90.0, date=datetime(2026, 3, 31, tzinfo=UTC),
        import_batch_id=batch_id, client_request_id="casbal:undo",
    )
    assert remove_import_batch(db_session, UID, batch_id) == 1
    row = _holding(db_session, "UNDO")
    assert row is not None
    assert (_f(row.shares), _f(row.buy_price)) == (5.0, 100.0)


def test_remove_import_batch_that_would_oversell_raises(db_session):
    _write(db_session, "OVER", "BUY", 5.0, 100.0, date=datetime(2026, 1, 5, tzinfo=UTC))
    batch_id = _batch(db_session)
    restate_position(
        db_session, UID, "OVER", 20.0, 10.0, date=datetime(2026, 3, 31, tzinfo=UTC),
        import_batch_id=batch_id, client_request_id="casbal:over",
    )
    _write(db_session, "OVER", "SELL", 15.0, 12.0, date=datetime(2026, 5, 4, tzinfo=UTC))
    db_session.commit()

    with pytest.raises(LedgerError):
        remove_import_batch(db_session, UID, batch_id)
    db_session.rollback()
    row = _holding(db_session, "OVER")
    assert row is not None and _f(row.shares) == 5.0
    assert db_session.query(Transaction).filter_by(import_batch_id=batch_id).count() == 1


# ---------------------------------------------------------------------------
# Retired multi-asset POST
# ---------------------------------------------------------------------------

def test_multi_asset_post_is_retired(client, auth_headers, test_user_id):
    response = client.post(
        "/portfolio/multi-asset/transaction",
        json={"user_id": test_user_id, "asset_type": "MF", "symbol": ISIN, "transaction_type": "BUY",
              "quantity": 1, "price": 10.0},
        headers=auth_headers,
    )
    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "ENDPOINT_RETIRED"
