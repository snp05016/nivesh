"""DB-08/09/10: constraints declared on the models must exist in a database
built only by `alembic upgrade head`, and the new revisions must repair a
database that predates them. Alembic never compares CHECK constraints, so
these tests are the drift guard."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

PRE_FIX_REVISION = "25342fdfb06f"  # head before 61bba5810e8e (DB-06..DB-10 revisions)


def _alembic(db_path, *args):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND_DIR), capture_output=True, text=True, env=env,
    )


@pytest.fixture
def migrated(tmp_path):
    db = tmp_path / "schema.db"
    result = _alembic(db, "upgrade", "head")
    assert result.returncode == 0, result.stderr
    engine = create_engine(f"sqlite:///{db}")
    yield engine
    engine.dispose()


def _legacy_price_targets(conn) -> None:
    """Rebuild price_targets without ck_price_targets_positive, as on databases
    upgraded through the old chain."""
    conn.execute(text("ALTER TABLE price_targets RENAME TO price_targets_old"))
    conn.execute(text(
        "CREATE TABLE price_targets (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), "
        "ticker VARCHAR(30) NOT NULL, target_price FLOAT NOT NULL, direction VARCHAR(10) NOT NULL, "
        "triggered BOOLEAN, created_at DATETIME)"
    ))
    conn.execute(text("DROP TABLE price_targets_old"))
    conn.execute(text("INSERT INTO users (id, username, password_hash, display_name) VALUES (1, 'u1', 'x', 'U1')"))


def test_check_constraints_match_models(migrated):
    from sqlalchemy import CheckConstraint
    from models.db_models import Base  # pyright: ignore[reportMissingImports]

    insp = inspect(migrated)
    model = {
        c.name for t in Base.metadata.tables.values() for c in t.constraints
        if isinstance(c, CheckConstraint) and isinstance(c.name, str)
    }
    db = {c["name"] for t in Base.metadata.tables for c in insp.get_check_constraints(t) if c["name"]}
    assert model == db, f"missing: {sorted(model - db)}, extra: {sorted(db - model)}"
    assert {
        "ck_portfolio_transactions_quantity_nonneg",
        "ck_portfolio_transactions_price_nonneg",
        "ck_portfolio_transactions_type",
    } <= db


def test_foreign_keys_match_models(migrated):
    from models.db_models import Base  # pyright: ignore[reportMissingImports]

    insp = inspect(migrated)
    model = {
        (t.name, fk.parent.name, fk.column.table.name)
        for t in Base.metadata.tables.values() for fk in t.foreign_keys
    }
    db = {
        (t, col, fk["referred_table"])
        for t in Base.metadata.tables for fk in insp.get_foreign_keys(t)
        for col in fk["constrained_columns"]
    }
    assert model == db, f"missing: {sorted(model - db)}, extra: {sorted(db - model)}"


def test_new_indexes_and_columns_present(migrated):
    insp = inspect(migrated)
    assert "uq_portfolio_groups_one_default" in {ix["name"] for ix in insp.get_indexes("portfolio_groups")}
    assert "uq_portfolio_transactions_client_req" in {ix["name"] for ix in insp.get_indexes("portfolio_transactions")}
    assert "uq_kyc_consents_active" in {ix["name"] for ix in insp.get_indexes("kyc_consents")}
    assert "client_request_id" in {c["name"] for c in insp.get_columns("portfolio_transactions")}
    assert "deleted_at" in {c["name"] for c in insp.get_columns("users")}


def test_device_binding_unique_on_bindings_only(migrated):
    insp = inspect(migrated)
    assert "uq_device_binding_user_device" in {u["name"] for u in insp.get_unique_constraints("device_bindings")}
    assert not insp.get_unique_constraints("device_binding_attempts")


def test_ledger_rejects_bad_type(migrated):
    with migrated.begin() as conn:
        conn.execute(text("INSERT INTO users (id, username, password_hash, display_name) VALUES (1, 'u1', 'x', 'U1')"))
    with pytest.raises(IntegrityError):
        with migrated.begin() as conn:
            conn.execute(text(
                "INSERT INTO portfolio_transactions (user_id, ticker, transaction_type, quantity, price) "
                "VALUES (1, 'TCS', 'FOO', 1, 100)"
            ))


def test_upgrade_repairs_pre_fix_database(tmp_path):
    db = tmp_path / "legacy.db"
    assert _alembic(db, "upgrade", PRE_FIX_REVISION).returncode == 0
    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        _legacy_price_targets(conn)
        conn.execute(text(
            "INSERT INTO portfolio_groups (id, user_id, name, is_default) VALUES (1, 1, 'Core Holdings', 1), "
            "(2, 1, 'Legacy Holdings', 1)"
        ))
        conn.execute(text(
            "INSERT INTO kyc_consents (id, user_id, consent_type, granted) VALUES (1, 1, 'credit_check', 1), "
            "(2, 1, 'credit_check', 1)"
        ))
    assert "ck_price_targets_positive" not in {c["name"] for c in inspect(engine).get_check_constraints("price_targets")}

    result = _alembic(db, "upgrade", "head")

    assert result.returncode == 0, result.stderr
    insp = inspect(engine)
    assert "ck_price_targets_positive" in {c["name"] for c in insp.get_check_constraints("price_targets")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT id FROM portfolio_groups WHERE is_default = 1")).scalars().all() == [1]
        assert conn.execute(text(
            "SELECT id FROM kyc_consents WHERE granted = 1 AND revoked_at IS NULL"
        )).scalars().all() == [2]
    engine.dispose()


def test_upgrade_stops_on_violating_rows(tmp_path):
    db = tmp_path / "violating.db"
    assert _alembic(db, "upgrade", PRE_FIX_REVISION).returncode == 0
    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        _legacy_price_targets(conn)
        conn.execute(text(
            "INSERT INTO price_targets (user_id, ticker, target_price, direction) VALUES (1, 'TCS', 0, 'above')"
        ))
    engine.dispose()

    result = _alembic(db, "upgrade", "head")

    assert result.returncode != 0
    assert "ck_price_targets_positive" in result.stdout + result.stderr
