import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import json

from repositories.job_repo import (
    create_job,
    get_job,
    update_job,
    append_checkpoint,
    add_job_tokens,
    get_active_job_for_user,
    list_monitor_jobs,
    sweep_stale_jobs
)

@pytest.fixture
def mock_session_ctx():
    session = MagicMock()
    ctx = MagicMock()
    ctx.__enter__.return_value = session
    with patch("repositories.job_repo._get_session", return_value=ctx):
        yield session

def test_create_job(mock_session_ctx):
    res = create_job(1, "RELIANCE", "NSE", "standard")
    assert res["ticker"] == "RELIANCE"
    assert res["status"] == "QUEUED"
    assert res["scan_type"] == "standard"
    assert mock_session_ctx.add.called
    assert mock_session_ctx.commit.called

def test_get_job_exists(mock_session_ctx):
    job = MagicMock(
        job_id="123", 
        status="SUCCEEDED", 
        result_json=json.dumps({"test": 1}), 
        checkpoints="[]", 
        created_at=None, 
        started_at=None, 
        finished_at=None,
        heartbeat_at=None,
        user_id=1,
        ticker="RELIANCE",
        exchange="NSE",
        scan_type="standard",
        stage="final",
        progress_pct=100,
        pid=1234,
        tokens_used=1000,
        error=None
    )
    mock_session_ctx.get.return_value = job
    
    res = get_job("123")
    assert res is not None
    assert res["job_id"] == "123"
    assert res["result"]["test"] == 1

def test_update_job(mock_session_ctx):
    # Compare-and-set: query(AnalysisJob).filter(job_id, status active).update(fields)
    upd = mock_session_ctx.query.return_value.filter.return_value.update
    upd.return_value = 1

    assert update_job("123", status="SUCCEEDED") is True
    fields = upd.call_args.args[0]
    assert fields["status"] == "SUCCEEDED"
    assert "finished_at" in fields and "heartbeat_at" in fields
    assert mock_session_ctx.commit.called

    upd.return_value = 0  # terminal row: not overwritten
    assert update_job("123", status="SUCCEEDED") is False

def test_append_checkpoint(mock_session_ctx):
    job = MagicMock(job_id="123", status="RUNNING", checkpoints="[]", progress_pct=0)
    locked = mock_session_ctx.query.return_value.filter.return_value.with_for_update.return_value
    locked.first.return_value = job

    append_checkpoint("123", stage="test", agent="agent", message="msg", state="ok", pct=50)
    assert job.stage == "test"
    assert job.progress_pct == 50
    assert mock_session_ctx.commit.called

def test_append_checkpoint_skips_terminal(mock_session_ctx):
    job = MagicMock(job_id="123", status="CANCELLED", checkpoints="[]", progress_pct=0, stage=None)
    locked = mock_session_ctx.query.return_value.filter.return_value.with_for_update.return_value
    locked.first.return_value = job

    append_checkpoint("123", stage="test", agent="agent", message="msg", state="ok", pct=50)
    assert job.stage is None
    assert not mock_session_ctx.commit.called

def test_sweep_stale_jobs(mock_session_ctx):
    # query(job_id, pid).filter().all() -> stale rows; then a CAS update on the dead ones
    mock_filter = mock_session_ctx.query.return_value.filter.return_value
    mock_filter.all.return_value = [("j1", None)]
    mock_filter.update.return_value = 1

    count = sweep_stale_jobs(90)
    assert count == 1
    fields = mock_filter.update.call_args.args[0]
    assert fields["status"] == "FAILED"
    assert fields["error"] == "Worker died (stale heartbeat / server restart)"
    assert mock_session_ctx.commit.called
