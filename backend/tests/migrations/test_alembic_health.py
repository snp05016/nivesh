"""Migration health tests — upgrade to head, model/DB drift detection."""
import os
import sys
import subprocess
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))
PYTHON = sys.executable


@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / "test_migration.db"
    yield db_path
    db_path.unlink(missing_ok=True)


def test_alembic_upgrade_head_from_empty(tmp_db):
    """Migration chain must succeed on a fresh empty DB."""
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_db}"}
    result = subprocess.run(
        [PYTHON, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND_DIR),
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, f"alembic upgrade head failed:\n{result.stderr}"


def test_alembic_at_head_after_upgrade(tmp_db):
    """After upgrade, alembic current must report (head)."""
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_db}"}
    subprocess.run([PYTHON, "-m", "alembic", "upgrade", "head"],
                   cwd=str(BACKEND_DIR), capture_output=True, env=env)
    result = subprocess.run(
        [PYTHON, "-m", "alembic", "current"],
        cwd=str(BACKEND_DIR), capture_output=True, text=True, env=env,
    )
    assert "head" in result.stdout, f"DB not at head: {result.stdout}"


def test_no_model_migration_drift(tmp_db):
    """After running all migrations, no columns should be missing from the DB."""
    from sqlalchemy import create_engine, inspect

    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_db}"}
    subprocess.run([PYTHON, "-m", "alembic", "upgrade", "head"],
                   cwd=str(BACKEND_DIR), capture_output=True, env=env)

    from models.db_models import Base

    engine = create_engine(f"sqlite:///{tmp_db}")
    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names()) - {"alembic_version"}
    model_tables = set(Base.metadata.tables.keys())

    missing_tables = model_tables - db_tables
    assert not missing_tables, f"Tables missing from migrated DB: {missing_tables}"

    missing_cols: dict[str, list] = {}
    for table in model_tables & db_tables:
        db_cols = {c["name"] for c in inspector.get_columns(table)}
        model_cols = {c.name for c in Base.metadata.tables[table].columns}
        missing = model_cols - db_cols
        if missing:
            missing_cols[table] = sorted(missing)

    assert not missing_cols, f"Missing columns in migrated DB: {missing_cols}"


def test_single_migration_head():
    """Ensure the Alembic migration graph has exactly one head (no unmerged branches)."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    alembic_ini_path = BACKEND_DIR / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    # Explicitly set the script_location to avoid parsing issues with %(here)s in testing
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))

    script = ScriptDirectory.from_config(alembic_cfg)
    heads = script.get_heads()

    assert len(heads) == 1, f"Expected exactly 1 migration head, but found {len(heads)}: {heads}"


ROOT_REVISION_FILE = BACKEND_DIR / "migrations" / "versions" / "0dc3e605ea33_initial_schema.py"


def _alembic(db_path, *args):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
    return subprocess.run(
        [PYTHON, "-m", "alembic", *args],
        cwd=str(BACKEND_DIR), capture_output=True, text=True, env=env,
    )


def test_root_revision_is_frozen_ddl():
    """DB-07: the baseline must be explicit DDL, not create_all() of today's models."""
    import ast

    tree = ast.parse(ROOT_REVISION_FILE.read_text())
    model_imports = [
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("models")
    ]
    metadata_calls = [
        node.attr for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in ("create_all", "drop_all")
    ]
    assert not model_imports, f"root revision imports app models: {model_imports}"
    assert not metadata_calls, f"root revision calls {metadata_calls}"


def test_root_downgrade_raises(tmp_db):
    """Downgrading the baseline must refuse instead of dropping every table."""
    up = _alembic(tmp_db, "upgrade", "0dc3e605ea33")
    assert up.returncode == 0, up.stderr
    down = _alembic(tmp_db, "downgrade", "base")
    assert down.returncode != 0
    assert "cannot be downgraded" in down.stdout + down.stderr


def test_watchlists_created_for_db_missing_it(tmp_db):
    """117b4057d650 must create watchlists on a DB built before the model existed."""
    from sqlalchemy import create_engine, inspect, text

    assert _alembic(tmp_db, "upgrade", "t4u5v6w7x8y9").returncode == 0
    engine = create_engine(f"sqlite:///{tmp_db}")
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE watchlists"))
    assert "watchlists" not in inspect(engine).get_table_names()

    result = _alembic(tmp_db, "upgrade", "head")
    assert result.returncode == 0, result.stderr
    insp = inspect(engine)
    assert "watchlists" in insp.get_table_names()
    assert {ix["name"] for ix in insp.get_indexes("watchlists")} == {
        "ix_watchlists_id", "ix_watchlists_user_id", "ix_watchlists_ticker",
    }
    engine.dispose()


def test_named_indexes_and_constraints_match_models(tmp_db):
    """A DB built only by migrations must carry every named index/constraint of the models."""
    from sqlalchemy import CheckConstraint, UniqueConstraint, create_engine, inspect

    assert _alembic(tmp_db, "upgrade", "head").returncode == 0
    from models.db_models import Base

    insp = inspect(create_engine(f"sqlite:///{tmp_db}"))
    problems = {}
    for name, table in Base.metadata.tables.items():
        model_ix = {ix.name for ix in table.indexes if isinstance(ix.name, str)}
        db_ix = {ix["name"] for ix in insp.get_indexes(name)}
        model_uq = {c.name for c in table.constraints if isinstance(c, UniqueConstraint) and isinstance(c.name, str)}
        db_uq = {c["name"] for c in insp.get_unique_constraints(name) if c["name"]}
        model_ck = {c.name for c in table.constraints if isinstance(c, CheckConstraint) and isinstance(c.name, str)}
        db_ck = {c["name"] for c in insp.get_check_constraints(name) if c["name"]}
        diff = {
            kind: (sorted(map(str, model - db)), sorted(map(str, db - model)))
            for kind, model, db in (("index", model_ix, db_ix), ("unique", model_uq, db_uq), ("check", model_ck, db_ck))
            if model != db
        }
        if diff:
            problems[name] = diff
    assert not problems, f"(missing, extra) per table: {problems}"
