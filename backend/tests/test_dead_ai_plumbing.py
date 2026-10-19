"""LLM-26: dead or misnamed AI plumbing stays gone (static AST checks, no imports)."""
import ast
from pathlib import Path

SERVICES = Path(__file__).resolve().parent.parent / "services"


def _defined_names(filename: str) -> set[str]:
    tree = ast.parse((SERVICES / filename).read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
    return names


def test_orchestrator_has_no_uncalled_dlq():
    names = _defined_names("orchestrator.py")
    assert not {"enqueue_dlq", "drain_dlq", "_DLQ_PATH", "_DLQ_LOCK"} & names


def test_celery_analysis_task_is_gone():
    # The task called analyze() without the required exchange argument; REL-12
    # deleted the module. It must not come back with the broken call.
    path = SERVICES / "celery_tasks.py"
    assert not path.exists() or "run_analysis_task" not in path.read_text()


def test_stance_extractor_is_not_named_after_haiku():
    names = _defined_names("advisor_harvester.py")
    assert "_extract_stance_llm" in names  # it calls DeepSeek, not Claude Haiku
    assert "_extract_stance_with_haiku" not in names


def test_advisor_harvest_cron_comment_matches_utc_schedule():
    # The scheduler runs in UTC: hour=1, minute=30 fires at 07:00 IST.
    line = next(
        ln for ln in (SERVICES / "harvest_worker.py").read_text().splitlines()
        if "add_job(_run_harvest_all_advisors" in ln
    )
    assert "hour=1" in line and "minute=30" in line
    assert "07:00 IST" in line
