"""GH-616: the route verifier must check paths that are actually registered."""
import importlib.util
from pathlib import Path

from fastapi import FastAPI

from main import app

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "verify_route_registration.py"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_route_registration", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # no side effects: main() only runs under __main__
    return module


def test_real_app_has_all_critical_routes():
    assert _load_verifier().find_route_issues(app) == []


def test_stub_app_reports_missing_critical_routes():
    verifier = _load_verifier()
    stub = FastAPI()

    @stub.get("/ping")
    def ping():
        return {}

    issues = verifier.find_route_issues(stub)
    expected = {f"Critical route missing: {p}" for p in verifier.CRITICAL_PATHS - {"/ping"}}
    assert set(issues) == expected
