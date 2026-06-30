import logging
#!/usr/bin/env python3
"""
Verify SQLAlchemy model metadata matches the migrated DB schema.

Creates a temporary DB, runs all Alembic migrations to head,
then compares the live schema against SQLAlchemy's metadata.

Exit 0 = no drift detected.
Exit 1 = drift detected or error.
"""

import os
import sys
import tempfile
from pathlib import Path

# Ensure backend root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Use a temp DB, not the real one
_tmp = tempfile.mktemp(suffix=".db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}")
os.environ.setdefault("ENABLE_SCHEDULER", "false")

try:
    import subprocess
    from sqlalchemy import create_engine, inspect, text

    BACKEND_DIR = Path(__file__).parent.parent
    PYTHON = sys.executable

    # Run alembic upgrade head on the temp DB
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{_tmp}"}
    result = subprocess.run(
        [PYTHON, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        logging.info(f"[DRIFT] alembic upgrade head FAILED:\n{result.stderr}")
        sys.exit(1)

    from models.db_models import Base

    # Inspect the migrated DB
    engine = create_engine(f"sqlite:///{_tmp}")
    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names())

    # Compare against ORM metadata
    model_tables = set(Base.metadata.tables.keys())
    # Exclude alembic_version from comparison
    db_tables.discard("alembic_version")

    missing_tables = model_tables - db_tables
    extra_tables = db_tables - model_tables

    drift_found = False
    missing_cols: dict[str, list[str]] = {}

    for table_name in model_tables & db_tables:
        db_cols = {c["name"] for c in inspector.get_columns(table_name)}
        model_cols = {c.name for c in Base.metadata.tables[table_name].columns}
        missing = model_cols - db_cols
        if missing:
            missing_cols[table_name] = sorted(missing)

    if missing_tables:
        logging.info(f"[DRIFT] Tables in model but not in DB: {sorted(missing_tables)}")
        drift_found = True
    if extra_tables:
        logging.info(f"[INFO]  Tables in DB but not in model (may be OK): {sorted(extra_tables)}")
    if missing_cols:
        for table, cols in missing_cols.items():
            logging.info(f"[DRIFT] Missing columns in '{table}': {cols}")
        drift_found = True

    if drift_found:
        logging.info("[DRIFT] Model/migration drift detected — run: alembic revision --autogenerate")
        sys.exit(1)
    else:
        logging.info("[OK] No model/migration drift detected")
        sys.exit(0)

finally:
    try:
        Path(_tmp).unlink(missing_ok=True)
    except Exception as _e:
        pass
