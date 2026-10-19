"""Data-cluster wiring: job registration, the failure-swallowing runner, router order and the removed bhavcopy job."""
import ast
import logging
import re
from pathlib import Path

import pytest
from starlette.routing import Match

from services import data_jobs

BACKEND = Path(__file__).resolve().parent.parent


class FakeScheduler:
    def __init__(self):
        self.jobs = []

    def add_job(self, func, trigger, **kwargs):
        self.jobs.append((func, trigger, kwargs))


def test_registers_seven_ist_jobs_with_safe_defaults():
    scheduler = FakeScheduler()
    ids = data_jobs.register_data_jobs(scheduler)
    assert ids == [
        "data_eod_mirror_evening", "data_eod_mirror_morning", "data_amfi_nav_night", "data_amfi_nav_morning",
        "data_equity_master", "data_results_feed", "data_results_numbers",
    ]
    assert len(scheduler.jobs) == 7
    for func, trigger, kwargs in scheduler.jobs:
        assert func is data_jobs.run_job and trigger == "cron"
        assert kwargs["timezone"] == "Asia/Kolkata" and kwargs["max_instances"] == 1
        assert kwargs["coalesce"] is True and kwargs["misfire_grace_time"] == 3600 and kwargs["replace_existing"]
        assert kwargs["args"][0] == kwargs["id"]
    by_id = {kw["id"]: kw for _, _, kw in scheduler.jobs}
    assert (by_id["data_eod_mirror_evening"]["day_of_week"], by_id["data_eod_mirror_evening"]["hour"],
            by_id["data_eod_mirror_evening"]["minute"]) == ("mon-fri", 21, 40)
    assert by_id["data_results_feed"]["hour"] == "8-23" and by_id["data_results_feed"]["minute"] == "5,35"


def test_every_target_resolves_to_a_callable():
    import importlib

    for _, target, _ in data_jobs.JOBS:
        module, func = target.split(":")
        assert callable(getattr(importlib.import_module(module), func)), target


def test_run_job_swallows_errors_and_records_one_diagnostic(monkeypatch, caplog):
    calls = []
    from services import error_telemetry

    monkeypatch.setattr(error_telemetry, "log_diagnostic_error", lambda **kw: calls.append(kw) or "id")
    monkeypatch.setattr("services.amfi.harvest", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    with caplog.at_level(logging.ERROR):
        data_jobs.run_job("data_amfi_nav_night", "services.amfi:harvest")  # must not raise
    assert calls == [{"subsystem": "DATA_FEEDS", "classification": "data_amfi_nav_night",
                      "context": {"error": "RuntimeError"}}]


def test_run_job_logs_the_result(monkeypatch, caplog):
    monkeypatch.setattr("services.amfi.harvest", lambda: {"skipped": "flag_off"})
    with caplog.at_level(logging.INFO, logger=data_jobs.logger.name):
        data_jobs.run_job("data_amfi_nav_night", "services.amfi:harvest")
    assert "flag_off" in caplog.text


def test_scheduler_registers_data_jobs_inside_try_before_start_and_bhavcopy_is_gone():
    source = (BACKEND / "services" / "harvest_worker.py").read_text()
    tree = ast.parse(source)
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "start_scheduler")

    def calls(node, name):
        return [c for c in ast.walk(node) if isinstance(c, ast.Call)
                and getattr(c.func, "id", getattr(c.func, "attr", None)) == name]

    guarded = [t for t in ast.walk(fn) if isinstance(t, ast.Try) and any(calls(s, "register_data_jobs") for s in t.body)]
    assert len(guarded) == 1
    assert any(isinstance(h.type, ast.Name) and h.type.id == "Exception" for h in guarded[0].handlers)
    starts = [c for c in calls(fn, "start") if getattr(c.func.value, "id", "") == "_scheduler"]
    assert starts and guarded[0].lineno < min(c.lineno for c in starts)
    assert "download_bhavcopy" not in source and "_run_bhavcopy_download" not in source
    assert "download_bhavcopy" not in (BACKEND / "services" / "nse_data_provider.py").read_text()


def test_no_download_bhavcopy_outside_tests():
    hits = [str(p.relative_to(BACKEND)) for p in BACKEND.rglob("*.py")
            if "tests" not in p.parts and "venv" not in p.parts and "download_bhavcopy" in p.read_text()]
    assert hits == []


def _first_full_match(app, path):
    scope = {"type": "http", "method": "GET", "path": path, "root_path": "", "query_string": b"", "headers": []}
    for route in app.router.routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return route
    return None


@pytest.mark.parametrize("path,module", [
    ("/api/v1/portfolio/corporate-actions", "routers.corporate_actions"),
    ("/api/v1/stocks/TCS/results-digest", "routers.results_digest"),
])
def test_data_routes_win_route_matching(path, module):
    from main import app

    route = _first_full_match(app, path)
    assert route is not None and route.endpoint.__module__ == module


def test_include_lines_precede_portfolio_and_stocks_routers():
    lines = (BACKEND / "main.py").read_text().splitlines()

    def index(pattern):
        for i, line in enumerate(lines):
            if re.match(pattern, line):
                return i
        return None

    ca, rd = index(r"app\.include_router\(corporate_actions\.router"), index(r"app\.include_router\(results_digest\.router")
    assert ca is not None and rd is not None
    for later in (index(r"app\.include_router\(portfolio\.router"), index(r"app\.include_router\(stocks\.router")):
        if later is not None:
            assert ca < later and rd < later
