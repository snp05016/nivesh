"""Stress-test job persistence and progress contracts."""


def test_prepare_stress_test_job_only_builds_durable_launch(monkeypatch):
    from services import stress_test_jobs

    holdings = [{"ticker": "TCS", "shares": 10.0, "buy_price": 100.0}]
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

    class FailingProcess:
        pid = None

        def __init__(self, **_kwargs):
            pass

        def start(self):
            raise RuntimeError("process table full")

    monkeypatch.setattr(
        stress_test_router,
        "prepare_stress_test_job",
        lambda *_args, **_kwargs: launch,
    )
    monkeypatch.setattr(
        stress_test_router.multiprocessing,
        "Process",
        FailingProcess,
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
    assert "process table full" in str(exc_info.value.detail)
    assert recorded == {
        "job_id": "stress-job-2",
        "error": "process table full",
    }


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
