"""Money C4 schema (revision ea2f610ceb51): asset_class, import batches, journal market score.

- upgrade head on a temp SQLite creates the columns, table, constraints and
  indexes; downgrading below ea2f610ceb51 removes them; upgrading again works;
- exactly one Alembic head;
- previews of one file may repeat, a second committed batch of it is refused;
- ON DELETE SET NULL on portfolio_transactions.import_batch_id;
- compliance_service.erase_user deletes a user's batches and imported rows.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
REVISION = "ea2f610ceb51"
DOWN_REVISION = "3b38ab41c39c"
SHA = "c0" * 32


def _alembic(db_path: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND_DIR), capture_output=True, text=True, env=env,
    )


def _script():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return ScriptDirectory.from_config(config)


def _schema(engine) -> dict:
    insp = sa.inspect(engine)
    tables = set(insp.get_table_names())
    out: dict = {"tables": tables}
    for table in ("portfolio_transactions", "portfolio", "trade_journal", "import_batches"):
        if table not in tables:
            continue
        out[table] = {
            "columns": {c["name"] for c in insp.get_columns(table)},
            "indexes": {ix["name"] for ix in insp.get_indexes(table)},
            "checks": {c["name"] for c in insp.get_check_constraints(table)},
            "fks": {fk["name"]: fk for fk in insp.get_foreign_keys(table) if fk["name"]},
        }
    return out


def _assert_upgraded(engine) -> None:
    s = _schema(engine)
    assert "import_batches" in s["tables"]
    tx = s["portfolio_transactions"]
    assert {"asset_class", "import_batch_id"} <= tx["columns"]
    assert "ck_portfolio_transactions_asset_class" in tx["checks"]
    assert "ix_portfolio_transactions_import_batch" in tx["indexes"]
    fk = tx["fks"]["fk_portfolio_transactions_import_batch"]
    assert fk["referred_table"] == "import_batches"
    assert (fk.get("options") or {}).get("ondelete") == "SET NULL"
    assert "asset_class" in s["portfolio"]["columns"]
    assert "ck_portfolio_asset_class" in s["portfolio"]["checks"]
    assert "market_score" in s["trade_journal"]["columns"]
    batches = s["import_batches"]
    assert {
        "id", "user_id", "source", "status", "file_sha256", "cas_type", "statement_from", "statement_to",
        "preview_json", "error_code", "schemes_total", "schemes_imported", "inserted_rows", "skipped_rows",
        "consent_notice_version", "consented_at", "created_at", "committed_at",
    } == batches["columns"]
    assert {"ix_import_batches_user_created", "uq_import_batches_user_file_committed"} <= batches["indexes"]
    assert "ck_import_batches_status" in batches["checks"]


def _assert_downgraded(engine) -> None:
    s = _schema(engine)
    assert "import_batches" not in s["tables"]
    tx = s["portfolio_transactions"]
    assert not {"asset_class", "import_batch_id"} & tx["columns"]
    assert "ck_portfolio_transactions_asset_class" not in tx["checks"]
    assert "ix_portfolio_transactions_import_batch" not in tx["indexes"]
    assert "fk_portfolio_transactions_import_batch" not in tx["fks"]
    # Earlier revisions' constraints survive the table rebuild.
    assert "ck_portfolio_transactions_type" in tx["checks"]
    assert "uq_portfolio_transactions_client_req" in tx["indexes"]
    assert "asset_class" not in s["portfolio"]["columns"]
    assert "ck_portfolio_asset_class" not in s["portfolio"]["checks"]
    assert "ck_portfolio_shares_positive" in s["portfolio"]["checks"]
    assert "market_score" not in s["trade_journal"]["columns"]


def test_exactly_one_head_and_revision_is_chained():
    script = _script()
    assert len(script.get_heads()) == 1
    rev = script.get_revision(REVISION)
    assert rev is not None and rev.down_revision == DOWN_REVISION


def test_upgrade_downgrade_upgrade(tmp_path):
    db = tmp_path / "money_schema.db"
    up = _alembic(db, "upgrade", "head")
    assert up.returncode == 0, up.stderr
    engine = sa.create_engine(f"sqlite:///{db}")
    try:
        _assert_upgraded(engine)
        with engine.begin() as conn:
            conn.execute(sa.text(
                "INSERT INTO users (id, username, password_hash, display_name) VALUES (1, 'm1', 'x', 'M')"
            ))
            conn.execute(sa.text(
                "INSERT INTO portfolio_transactions (user_id, ticker, transaction_type, quantity, price, fees) "
                "VALUES (1, 'INFY', 'BUY', 1, 10, 0)"
            ))
        with engine.connect() as conn:
            assert conn.execute(sa.text("SELECT asset_class FROM portfolio_transactions")).scalar() == "EQ"
        engine.dispose()

        down = _alembic(db, "downgrade", DOWN_REVISION)
        assert down.returncode == 0, down.stderr
        _assert_downgraded(engine)
        with engine.connect() as conn:
            assert conn.execute(sa.text("SELECT COUNT(*) FROM portfolio_transactions")).scalar() == 1
        engine.dispose()

        again = _alembic(db, "upgrade", "head")
        assert again.returncode == 0, again.stderr
        _assert_upgraded(engine)
    finally:
        engine.dispose()


def test_migrated_partial_unique_and_set_null(tmp_path):
    db = tmp_path / "money_constraints.db"
    assert _alembic(db, "upgrade", "head").returncode == 0
    engine = sa.create_engine(f"sqlite:///{db}")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    insert_batch = sa.text(
        "INSERT INTO import_batches (user_id, status, file_sha256, created_at) "
        "VALUES (1, :status, :sha, '2026-10-08 09:00:00')"
    )
    try:
        with engine.begin() as conn:
            conn.execute(sa.text(
                "INSERT INTO users (id, username, password_hash, display_name) VALUES (1, 'm2', 'x', 'M')"
            ))
            conn.execute(insert_batch, {"status": "previewed", "sha": SHA})
            conn.execute(insert_batch, {"status": "previewed", "sha": SHA})
            conn.execute(insert_batch, {"status": "committed", "sha": SHA})
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(insert_batch, {"status": "committed", "sha": SHA})
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(insert_batch, {"status": "imported", "sha": "d0" * 32})

        with engine.begin() as conn:
            batch_id = conn.execute(sa.text("SELECT MAX(id) FROM import_batches")).scalar()
            conn.execute(sa.text(
                "INSERT INTO portfolio_transactions (user_id, ticker, transaction_type, quantity, price, fees, "
                "asset_class, import_batch_id) VALUES (1, 'INF179K01VC4', 'ADJUST', 10, 50, 0, 'MF', :b)"
            ), {"b": batch_id})
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(sa.text(
                    "INSERT INTO portfolio_transactions (user_id, ticker, transaction_type, quantity, price, "
                    "fees, asset_class) VALUES (1, 'GOLD', 'BUY', 1, 1, 0, 'GOLD')"
                ))
        with engine.begin() as conn:
            conn.execute(sa.text("DELETE FROM import_batches WHERE id = :b"), {"b": batch_id})
        with engine.connect() as conn:
            assert conn.execute(sa.text("SELECT import_batch_id FROM portfolio_transactions")).all() == [(None,)]
    finally:
        engine.dispose()


def test_orm_committed_batch_is_unique_per_file():
    from models.db_models import Base, ImportBatch, User

    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        user = User(username="mf_batch_user", password_hash="x", display_name="MF")
        session.add(user)
        session.flush()
        session.add_all([
            ImportBatch(user_id=user.id, status="previewed", file_sha256=SHA),
            ImportBatch(user_id=user.id, status="previewed", file_sha256=SHA),
            ImportBatch(user_id=user.id, status="committed", file_sha256=SHA),
        ])
        session.flush()
        session.add(ImportBatch(user_id=user.id, status="committed", file_sha256=SHA))
        with pytest.raises(IntegrityError):
            session.flush()
    finally:
        session.close()
        engine.dispose()


def test_erase_user_deletes_batches_and_imported_rows():
    import database
    from models.db_models import ImportBatch, Portfolio, Transaction, User
    from services.compliance_service import erase_user

    with database.get_session() as session:
        user = User(username=f"erase_mf_{uuid4().hex[:12]}", password_hash="x", display_name="Erase MF")
        session.add(user)
        session.flush()
        uid = int(user.id)  # type: ignore[arg-type]
        batch = ImportBatch(
            user_id=uid, status="committed", file_sha256=uuid4().hex * 2,
            committed_at=datetime.now(timezone.utc),
        )
        session.add(batch)
        session.flush()
        session.add(Transaction(
            user_id=uid, ticker="INF179K01VC4", transaction_type="ADJUST", quantity=10.0, price=50.0,
            fees=0.0, asset_class="MF", import_batch_id=batch.id, client_request_id=f"casbal:{uuid4().hex}",
        ))
        session.add(Portfolio(
            user_id=uid, ticker="INF179K01VC4", company_name="HDFC Flexi Cap Fund", shares=10.0,
            buy_price=50.0, group_name="holdings", asset_class="MF",
        ))
        session.commit()

    result = erase_user(uid)

    assert result["tables"]["import_batches"] == 1
    assert result["tables"]["portfolio_transactions"] == 1
    with database.get_session() as session:
        assert session.query(ImportBatch).filter_by(user_id=uid).count() == 0
        assert session.query(Transaction).filter_by(user_id=uid).count() == 0
        # Core select: the ORM guard for fund rows (money-mf-isolation) never filters it.
        portfolio = Portfolio.__table__
        assert session.execute(
            sa.select(sa.func.count()).select_from(portfolio).where(portfolio.c.user_id == uid)
        ).scalar() == 0
