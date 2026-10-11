"""Stress-test job persistence and progress contracts."""


def test_prepare_stress_test_job_only_builds_durable_launch(monkeypatch):
    from services import stress_test_jobs

    holdings = [{"ticker": "TCS", "shares": 10.0, "buy_price": 100.0}]
    monkeypatch.setattr(
        stress_test_jobs.job_repo,
        "get_active_job_for_user_and_type",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        stress_test_jobs.stress_test_repo,
        "list_portfolio_holdings",
        lambda user_id, portfolio_id: holdings,
    )
    monkeypatch.setattr(
        stress_test_jobs.job_repo,
        "create_job",
        lambda *_args: {"job_id": "stress-job-1"},
    )
    monkeypatch.setattr(
        stress_test_jobs.job_repo,
        "append_checkpoint",
        lambda *_args, **_kwargs: None,
    )

    assert hasattr(stress_test_jobs, "prepare_stress_test_job")
    launch = stress_test_jobs.prepare_stress_test_job(
        user_id=7,
        portfolio_id="holdings",
        scenarios=["NIFTY_CRASH"],
    )

    assert launch.job_id == "stress-job-1"
    assert launch.holdings == holdings
    assert launch.scenarios == ["NIFTY_CRASH"]
    assert launch.completed_response is None


def test_start_endpoint_marks_durable_job_failed_when_process_spawn_fails(monkeypatch):
    import pytest
    from fastapi import HTTPException

    from routers import stress_test as stress_test_router
    from services.stress_test_jobs import StressTestLaunch

    launch = StressTestLaunch(
        job_id="stress-job-2",
        holdings=[{"ticker": "TCS", "shares": 10.0, "buy_price": 100.0}],
        scenarios=["NIFTY_CRASH"],
    )
    recorded = {}

    def failing_spawn(*_args, **_kwargs):
        raise RuntimeError("process table full")

    monkeypatch.setattr(
        stress_test_router,
        "prepare_stress_test_job",
        lambda *_args, **_kwargs: launch,
    )
    monkeypatch.setattr(
        stress_test_router.job_manager,
        "spawn_process",
        failing_spawn,
    )
    monkeypatch.setattr(
        stress_test_router,
        "mark_stress_test_start_failed",
        lambda job_id, error: recorded.update(job_id=job_id, error=str(error)),
    )

    request = stress_test_router.StressTestRequest(
        portfolio_id="holdings",
        scenarios=["NIFTY_CRASH"],
    )
    with pytest.raises(HTTPException) as exc_info:
        stress_test_router.start_stress_test(request, user_id=7)

    assert exc_info.value.status_code == 500
    # The owner-visible DB row keeps the cause; the HTTP detail does not leak it.
    assert "process table full" not in str(exc_info.value.detail)
    assert recorded == {
        "job_id": "stress-job-2",
        "error": "process table full",
    }


def test_second_stress_request_returns_existing_job(monkeypatch):
    from services import stress_test_jobs

    created = []
    monkeypatch.setattr(
        stress_test_jobs.job_repo,
        "get_active_job_for_user_and_type",
        lambda user_id, scan_type: {"job_id": "j1"},
    )
    monkeypatch.setattr(
        stress_test_jobs.job_repo,
        "create_job",
        lambda *args: created.append(args) or {"job_id": "new"},
    )

    launch = stress_test_jobs.prepare_stress_test_job(7, "holdings", ["NIFTY_CRASH"])

    assert launch.job_id == "j1"
    assert launch.completed_response == {"job_id": "j1", "status": "running"}
    assert created == []


def test_capacity_returns_429(monkeypatch):
    import pytest
    from fastapi import HTTPException

    from routers import stress_test as stress_test_router
    from services import job_manager
    from services.stress_test_jobs import StressTestLaunch

    launch = StressTestLaunch(
        job_id="stress-job-3",
        holdings=[{"ticker": "TCS", "shares": 10.0, "buy_price": 100.0}],
        scenarios=["NIFTY_CRASH"],
    )
    recorded = {}

    def no_process(*_args, **_kwargs):
        raise AssertionError("must not start a process when at capacity")

    monkeypatch.setattr(stress_test_router, "prepare_stress_test_job", lambda *_a, **_k: launch)
    monkeypatch.setattr(job_manager, "MAX_CONCURRENT_JOBS", 6)
    monkeypatch.setattr(
        job_manager.job_repo,
        "list_active_jobs",
        lambda: [{"job_id": f"busy-{i}", "created_at": None} for i in range(7)],
    )
    monkeypatch.setattr(job_manager.multiprocessing, "Process", no_process)
    monkeypatch.setattr(
        stress_test_router,
        "mark_stress_test_start_failed",
        lambda job_id, error: recorded.update(job_id=job_id),
    )

    request = stress_test_router.StressTestRequest(portfolio_id="holdings", scenarios=[])
    with pytest.raises(HTTPException) as exc_info:
        stress_test_router.start_stress_test(request, user_id=7)

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers == {"Retry-After": "30"}
    assert recorded == {"job_id": "stress-job-3"}


def test_scenarios_bounded():
    import pytest
    from pydantic import ValidationError

    from routers.stress_test import StressTestRequest

    StressTestRequest(portfolio_id="h", scenarios=["X"] * 20)
    with pytest.raises(ValidationError):
        StressTestRequest(portfolio_id="h", scenarios=["X"] * 21)


def test_spawn_registers_process_and_shutdown_terminates(monkeypatch):
    from services import job_manager

    created = []

    class FakeProc:
        def __init__(self, target=None, args=(), daemon=None):
            self.pid = 123
            self.daemon = daemon
            self.terminated = False
            created.append(self)

        def start(self):
            pass

        def is_alive(self):
            return not self.terminated

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.terminated = True

        def join(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr(job_manager.multiprocessing, "Process", FakeProc)
    monkeypatch.setattr(job_manager.job_repo, "list_active_jobs", lambda: [])

    assert job_manager.spawn_process("j2", lambda: None, ()) == 123
    proc = created[0]
    with job_manager._registry_lock:
        assert job_manager._job_registry["j2"] is proc
    assert proc.daemon is True

    job_manager.shutdown_all()
    assert proc.terminated
    assert "j2" not in job_manager._job_registry


def test_capacity_ignores_own_and_stale_rows(monkeypatch):
    from datetime import datetime, timedelta, timezone

    from services import job_manager

    old = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(tzinfo=None).isoformat()
    fresh = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(
        job_manager.job_repo,
        "list_active_jobs",
        lambda: [
            {"job_id": "mine", "created_at": fresh},
            {"job_id": "dead", "created_at": old},
            {"job_id": "live", "created_at": fresh},
        ],
    )

    assert job_manager._active_job_count("mine") == 1


def test_running_job_is_visible_from_any_api_worker(client, auth_headers, test_user_id):
    import database

    job = database.create_job(
        test_user_id,
        "PORTFOLIO",
        "NSE",
        "stress_test",
    )
    database.update_job(
        job["job_id"],
        status="RUNNING",
        progress_pct=58,
        stage="covariance",
    )
    database.append_checkpoint(
        job["job_id"],
        stage="covariance",
        agent="Stress Test Engine",
        message="Building historical covariance matrix",
        state="running",
        pct=58,
    )

    response = client.get(
        f"/api/v1/portfolio/stress-test/{job['job_id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "running",
        "progress_pct": 58,
        "stage": "Building historical covariance matrix",
        "checkpoint": "covariance",
    }
    # Free the user's single active stress_test slot for the next test.
    database.update_job(job["job_id"], status="SUCCEEDED")


def test_dashboard_lists_db_backed_stress_jobs(client, auth_headers, test_user_id):
    import database

    job = database.create_job(
        test_user_id,
        "PORTFOLIO",
        "NSE",
        "stress_test",
    )
    database.update_job(
        job["job_id"],
        status="RUNNING",
        progress_pct=72,
        stage="scenarios",
    )

    response = client.get(
        "/api/v1/dashboard/stress-test-jobs",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_count"] >= 1
    assert any(
        row["job_id"] == job["job_id"]
        and row["progress_pct"] == 72
        and row["stage"] == "scenarios"
        for row in payload["jobs"]
    )
    database.update_job(job["job_id"], status="SUCCEEDED")


def test_engine_emits_real_phase_progress(monkeypatch):
    import numpy as np

    from services import stress_test
    from services.math_engines import covariance

    enriched = [{
        "ticker": "TCS",
        "company_name": "Tata Consultancy Services",
        "shares": 10.0,
        "price": 100.0,
        "value": 1000.0,
        "yf_symbol": "TCS.NS",
        "betas": {"market": 1.0, "market_beta_source": "estimated"},
        "sector": "IT",
        "size_bucket": "large",
        "fallback_daily_vol": 0.015,
        "avg_daily_volume": 1_000_000.0,
        "spread_bps": 0.0005,
        "price_source": "live",
        "adv_source": "info",
    }]
    monkeypatch.setattr(stress_test, "enrich_holdings", lambda *_args, **_kwargs: enriched)
    monkeypatch.setattr(
        covariance,
        "fetch_historical_returns",
        lambda *_args, **_kwargs: {"TCS.NS": np.linspace(-0.01, 0.01, 30)},
    )

    events = []
    results = stress_test.run_stress_test(
        [],
        ["NIFTY_CRASH"],
        phase_callback=lambda checkpoint, pct, message: events.append(
            (checkpoint, pct, message)
        ),
    )

    checkpoints = [checkpoint for checkpoint, _pct, _message in events]
    percentages = [pct for _checkpoint, pct, _message in events]
    assert results
    assert "covariance" in checkpoints
    assert "scenarios" in checkpoints
    assert "scoring" in checkpoints
    assert percentages == sorted(percentages)


def test_beta_estimation_defaults_sector_for_fallback(monkeypatch):
    from services import stress_test
    from services.math_engines.vasicek import MacroBetasResponse

    seen = {}

    def fake_betas(ticker, sector):
        seen["sector"] = sector
        return MacroBetasResponse(
            market=1.0, midcap=0.0, smallcap=0.0, oil=0.0, rates=0.0,
            fx=0.0, inflation=0.0, fii_flow=0.0, dii_flow=0.0,
        )

    monkeypatch.setattr(stress_test, "get_adjusted_macro_betas", fake_betas)

    betas = stress_test._estimate_betas("UNKNOWN")
    assert seen["sector"] == "Other"
    # Engine consumers index and .get() the betas, so they must be a plain dict.
    assert isinstance(betas, dict)
    assert betas["market"] == 1.0
