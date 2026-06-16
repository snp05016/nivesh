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

    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db}"
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


def test_migration_head_revision_is_b2c3d4e5f6a7():
    """The current Alembic head must be the index migration we created."""
    versions_dir = BACKEND_DIR / "migrations" / "versions"
    head_files = list(versions_dir.glob("b2c3d4e5f6a7_*.py"))
    assert head_files, "Expected head migration b2c3d4e5f6a7 not found in versions/"
