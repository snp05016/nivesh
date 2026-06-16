"""Alembic migration chain tests and destructive-operation audit."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "versions"
BACKEND_ROOT = Path(__file__).resolve().parents[1]
DESTRUCTIVE_TOKENS = ("drop_table(", "drop_column(", "drop_constraint(")


def _load_revision(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_alembic_files_exist_and_have_single_head_chain():
    files = sorted(MIGRATIONS_DIR.glob("*.py"))
    assert files, "backend/migrations/versions must contain migration files"

    revisions = {}
    down_revisions = {}
    for path in files:
        module = _load_revision(path)
        assert module.revision
        assert module.revision not in revisions, f"duplicate revision {module.revision}"
        revisions[module.revision] = path.name
        down_revisions[module.revision] = module.down_revision

    heads = [
        revision
        for revision in revisions
        if revision not in {
            parent
            for parent in down_revisions.values()
            if isinstance(parent, str)
        }
    ]
    roots = [revision for revision, parent in down_revisions.items() if parent is None]

    assert len(roots) == 1
    assert len(heads) == 1


def test_all_non_root_down_revisions_exist():
    revisions = {}
    for path in sorted(MIGRATIONS_DIR.glob("*.py")):
        module = _load_revision(path)
        revisions[module.revision] = module.down_revision

    missing = {
        revision: down_revision
        for revision, down_revision in revisions.items()
        if isinstance(down_revision, str) and down_revision not in revisions
    }
    assert missing == {}


def test_migrations_include_upgrade_and_downgrade_functions():
    missing = []
    for path in sorted(MIGRATIONS_DIR.glob("*.py")):
        module = _load_revision(path)
        if not callable(getattr(module, "upgrade", None)) or not callable(getattr(module, "downgrade", None)):
            missing.append(path.name)

    assert missing == []


def test_destructive_migration_operations_are_visible_for_audit_report():
    destructive = {}
    for path in sorted(MIGRATIONS_DIR.glob("*.py")):
        text = path.read_text()
        hits = [token for token in DESTRUCTIVE_TOKENS if token in text]
        if hits:
            destructive[path.name] = hits

    assert destructive == {}


def test_alembic_empty_database_lifecycle(tmp_path):
    source_ini = BACKEND_ROOT / "alembic.ini"
    temp_ini = tmp_path / "alembic.ini"
    temp_db = tmp_path / "nivesh_migration_lifecycle.db"

    ini_text = source_ini.read_text()
    ini_text = ini_text.replace(
        "script_location = %(here)s/migrations",
        f"script_location = {BACKEND_ROOT / 'migrations'}",
    )
    ini_text = ini_text.replace(
        "sqlalchemy.url = sqlite:///./stockapp.db",
        f"sqlalchemy.url = sqlite:///{temp_db}",
    )
    temp_ini.write_text(ini_text)

    commands = [
        [sys.executable, "-m", "alembic", "-c", str(temp_ini), "upgrade", "head"],
        [sys.executable, "-m", "alembic", "-c", str(temp_ini), "downgrade", "-1"],
        [sys.executable, "-m", "alembic", "-c", str(temp_ini), "upgrade", "head"],
        [sys.executable, "-m", "alembic", "-c", str(temp_ini), "check"],
    ]
    for command in commands:
        result = subprocess.run(
            command,
            cwd=BACKEND_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        assert result.returncode == 0, result.stdout
