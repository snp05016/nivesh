"""ML-23: the backend Alpha158 feature stores are gone; ml-engine FeatureComputer
is the single feature definition and the backend persists no features."""
import ast
import importlib.util
from pathlib import Path

from models.db_models import Base

BACKEND_DIR = Path(__file__).resolve().parent.parent
DROP_MIGRATION = BACKEND_DIR / "migrations" / "versions" / "36e47c594dc7_drop_alpha158_feature_tables.py"


def _module_absent(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is None
    except ModuleNotFoundError:  # parent package (tasks) is gone too
        return True


def test_alpha158_tables_not_in_orm_metadata():
    assert "alpha158_features" not in Base.metadata.tables
    assert "alpha158_features_normalized" not in Base.metadata.tables


def test_alpha158_pipelines_removed():
    assert _module_absent("tasks.alpha158_task")
    assert _module_absent("services.nightly_pipeline")


def test_celery_module_has_no_materialization_task():
    # REL-12 deleted the unused Celery module outright.
    assert _module_absent("services.celery_tasks")


def test_drop_migration_drops_both_tables():
    tree = ast.parse(DROP_MIGRATION.read_text())
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    upgrade_strings = {
        n.value for n in ast.walk(funcs["upgrade"])
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }
    assert {"alpha158_features", "alpha158_features_normalized"} <= upgrade_strings
    assert "downgrade" in funcs
