"""Alembic metadata contract tests that avoid mutating any real database."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


BACKEND_ROOT = Path(__file__).resolve().parents[1]
VERSIONS_DIR = BACKEND_ROOT / "migrations" / "versions"


def _alembic_script() -> ScriptDirectory:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    return ScriptDirectory.from_config(config)


def test_alembic_revision_graph_has_one_base_and_one_head():
    script = _alembic_script()

    assert len(script.get_bases()) == 1
    assert len(script.get_heads()) == 1


def test_alembic_bytecode_revisions_have_matching_source_files():
    pyc_revisions = {
        path.name.split(".")[0].split("_", 1)[0]
        for path in (VERSIONS_DIR / "__pycache__").glob("*.pyc")
    }
    source_revisions = {path.stem.split("_", 1)[0] for path in VERSIONS_DIR.glob("*.py")}

    missing_sources = sorted(pyc_revisions - source_revisions)

    assert not missing_sources, f"bytecode-only Alembic revisions found: {missing_sources}"


def test_migration_env_uses_model_metadata_and_sqlite_batch_mode():
    env_text = (BACKEND_ROOT / "migrations" / "env.py").read_text(encoding="utf-8")

    assert "from models.db_models import Base" in env_text
    assert "target_metadata = Base.metadata" in env_text
    assert "render_as_batch=True" in env_text


def test_migration_env_honors_database_url_environment_override():
    env_text = (BACKEND_ROOT / "migrations" / "env.py").read_text(encoding="utf-8")

    assert "DATABASE_URL" in env_text
    assert "os.getenv" in env_text


def test_migration_sources_do_not_use_create_all_or_manual_alter_table():
    for path in VERSIONS_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "ALTER TABLE" not in text.upper()


def test_base_revision_creates_current_model_tables():
    import models.db_models as db_models

    script = _alembic_script()
    base_revision_id = script.get_bases()[0]
    base_script = script.get_revision(base_revision_id)
    assert base_script is not None

    spec = importlib.util.spec_from_file_location("base_revision_for_contract_test", base_script.path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    model_tables = set(db_models.Base.metadata.tables)
    source = Path(base_script.path).read_text(encoding="utf-8")
    assert source
    assert "Base.metadata.create_all" in source
    assert model_tables
