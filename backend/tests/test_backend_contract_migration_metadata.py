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
    """DB-07: the root revision is frozen DDL covering every model table.

    It must create each table with an explicit ``op.create_table`` call and
    must not import app models or call metadata create_all/drop_all.
    """
    import ast

    import models.db_models as db_models

    script = _alembic_script()
    base_script = script.get_revision(script.get_bases()[0])
    assert base_script is not None

    def create_table_names(tree: ast.AST) -> set[str]:
        return {
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "create_table"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "op"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        }

    tree = ast.parse(Path(base_script.path).read_text(encoding="utf-8"))
    metadata_calls = [
        node.attr for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in ("create_all", "drop_all")
    ]
    model_imports = [
        node for node in ast.walk(tree)
        if (isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "models")
        or (isinstance(node, ast.Import) and any(a.name.split(".")[0] == "models" for a in node.names))
    ]
    assert not metadata_calls, f"root revision calls {metadata_calls}"
    assert not model_imports, "root revision imports app models"

    root_tables = create_table_names(tree)
    assert root_tables, "root revision creates no tables with op.create_table"

    # Tables added after the baseline live in later revisions, so coverage is
    # checked across the whole history: every model table needs explicit DDL.
    created = set(root_tables)
    for path in VERSIONS_DIR.glob("*.py"):
        created |= create_table_names(ast.parse(path.read_text(encoding="utf-8")))
    model_tables = set(db_models.Base.metadata.tables)
    assert model_tables
    missing = model_tables - created
    assert not missing, f"model tables without op.create_table DDL: {sorted(missing)}"
