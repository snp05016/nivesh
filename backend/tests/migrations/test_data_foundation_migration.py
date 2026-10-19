"""Data-foundation migration: upgrade / downgrade / upgrade on a temp SQLite DB."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

BACKEND_DIR = Path(__file__).parent.parent.parent
REVISION = "ecac0bc9105a"
TABLES = {"instruments", "instrument_aliases", "daily_prices", "corporate_action_applications", "results_digests"}


def _alembic(db_path, *args):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=str(BACKEND_DIR),
                          capture_output=True, text=True, env=env)


@pytest.fixture
def tmp_db(tmp_path):
    return tmp_path / "data_foundation.db"


def test_upgrade_downgrade_upgrade(tmp_db):
    assert _alembic(tmp_db, "upgrade", "head").returncode == 0
    down = _alembic(tmp_db, "downgrade", "-1")
    assert down.returncode == 0, down.stderr
    engine = create_engine(f"sqlite:///{tmp_db}")
    assert not TABLES & set(inspect(engine).get_table_names())
    assert "scheme_type" not in {c["name"] for c in inspect(engine).get_columns("mutual_funds")}
    up = _alembic(tmp_db, "upgrade", "head")
    assert up.returncode == 0, up.stderr


def test_tables_columns_and_indexes_exist(tmp_db):
    assert _alembic(tmp_db, "upgrade", "head").returncode == 0
    insp = inspect(create_engine(f"sqlite:///{tmp_db}"))
    assert TABLES <= set(insp.get_table_names())
    cols = lambda t: {c["name"] for c in insp.get_columns(t)}  # noqa: E731
    assert {"event", "quality_flags"} <= cols("daily_prices")
    assert "group_id" in cols("corporate_action_applications")
    assert {"scheme_type", "is_active", "track_nav", "nav_source"} <= cols("mutual_funds")
    assert {"action_type", "ex_on", "ratio", "source", "nse_confirmed", "updated_at"} <= cols("corporate_actions")
    with create_engine(f"sqlite:///{tmp_db}").connect() as conn:
        sql = conn.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE name = 'uq_ca_applications_user_action_group'"
        ).scalar()
    assert sql and "UNIQUE" in sql.upper() and "coalesce(group_id, 0)" in sql
    ca_idx = {i["name"]: i for i in insp.get_indexes("corporate_actions")}
    assert ca_idx["uq_corporate_actions_ticker_type_ex"]["unique"]


def test_upgrade_is_idempotent_on_existing_objects(tmp_db):
    """Re-running the revision body over already-present tables must not fail."""
    assert _alembic(tmp_db, "upgrade", "head").returncode == 0
    assert _alembic(tmp_db, "stamp", "ea2f610ceb51").returncode == 0
    again = _alembic(tmp_db, "upgrade", "head")
    assert again.returncode == 0, again.stderr
