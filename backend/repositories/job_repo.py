"""AnalysisJob DAO — query functions extracted from database.py."""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from models.db_models import AnalysisJob


def _get_session():
    """Lazy import to avoid circular dependency with database module."""
    from database import get_session
    return get_session()


_JOB_TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED", "TIMEOUT"}
# Only these rows may still change; uq_analysis_jobs_active_user_scan allows one
# per (user_id, scan_type).
_JOB_ACTIVE = ("QUEUED", "RUNNING")

# Wall-clock budget per scan type (seconds). Single source: services.job_worker
# imports it for its kill-switch, and the staleness checks below add _STALE_GRACE
# (spawn delay) so a crashed worker never permanently blocks new runs.
WALLCLOCK_LIMITS: dict[str, int] = {"extreme": 600, "deep": 420, "standard": 420}
_STALE_GRACE = 60


def _stale_after_sec(scan_type: Optional[str] = None) -> int:
    """Age past which an active row cannot belong to a live worker (any type if None)."""
    limit = WALLCLOCK_LIMITS.get(scan_type, 300) if scan_type else max(WALLCLOCK_LIMITS.values())
    return limit + _STALE_GRACE


class JobAlreadyActive(Exception):
    """create_job lost to an active job of the same user and scan_type (`job`)."""

    def __init__(self, job: dict):
        super().__init__(f"active job {job['job_id']} already exists")
        self.job = job


def _parse_checkpoints(raw: str | None) -> list[dict]:
    try:
        parsed = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _job_to_dict(j: "AnalysisJob") -> dict:
    return {
        "job_id": j.job_id, "user_id": j.user_id, "ticker": j.ticker,
        "exchange": j.exchange, "scan_type": j.scan_type, "status": j.status,
        "stage": j.stage, "progress_pct": j.progress_pct,
        "checkpoints": _parse_checkpoints(j.checkpoints),
        "pid": j.pid, "tokens_used": j.tokens_used, "error": j.error,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "finished_at": j.finished_at.isoformat() if j.finished_at else None,
    }


def _job_to_monitor_dict(j: "AnalysisJob") -> dict:
    d = _job_to_dict(j)
    d["heartbeat_at"] = j.heartbeat_at.isoformat() if j.heartbeat_at else None
    d["result_json"] = j.result_json
    return d


def create_job(user_id: Optional[int], ticker: str, exchange: str, scan_type: str) -> dict:
    """Create a new analysis job and set its status to QUEUED.

    Args:
        user_id (Optional[int]): ID of the user requesting the job, or None.
        ticker (str): The stock ticker symbol.
        exchange (str): The exchange symbol.
        scan_type (str): The type of scan to perform.

    Returns:
        dict: A dictionary representation of the created AnalysisJob.

    Raises:
        JobAlreadyActive: the user already has a QUEUED/RUNNING job of this
            scan_type (enforced by the partial unique index, so concurrent
            requests cannot both insert).
    """
    jid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    with _get_session() as s:
        if user_id is not None:
            # A row past its wall-clock limit belongs to a dead worker; fail it in
            # this transaction so it cannot hold the unique index forever.
            stale_before = now - timedelta(seconds=_stale_after_sec(scan_type))
            (s.query(AnalysisJob)
               .filter(AnalysisJob.user_id == user_id,
                       AnalysisJob.scan_type == scan_type,
                       AnalysisJob.status.in_(_JOB_ACTIVE),
                       AnalysisJob.created_at < stale_before)
               .update({"status": "FAILED", "finished_at": now,
                        "error": "Stale: exceeded wall-clock limit"},
                       synchronize_session=False))
        j = AnalysisJob(job_id=jid, user_id=user_id, ticker=ticker.upper(),
                        exchange=exchange, scan_type=scan_type, status="QUEUED",
                        heartbeat_at=now)
        s.add(j)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            active = (s.query(AnalysisJob)
                        .filter(AnalysisJob.user_id == user_id,
                                AnalysisJob.scan_type == scan_type,
                                AnalysisJob.status.in_(_JOB_ACTIVE))
                        .order_by(AnalysisJob.created_at.desc()).first())
            if active is None:
                raise
            raise JobAlreadyActive(_job_to_dict(active)) from None
        return _job_to_dict(j)


def get_job(job_id: str) -> Optional[dict]:
    """Retrieve an analysis job by its ID.

    Args:
        job_id (str): The unique identifier of the job.

    Returns:
        Optional[dict]: A dictionary representation of the job, including the parsed result if successful, or None.
    """
    with _get_session() as s:
        j = s.get(AnalysisJob, job_id)
        if not j:
            return None
        d = _job_to_dict(j)
        if j.status == "SUCCEEDED" and j.result_json:
            try:
                d["result"] = json.loads(j.result_json)
            except Exception as _e:
                d["result"] = None
        return d


def update_job(job_id: str, **fields) -> bool:
    """Update fields of an active (QUEUED/RUNNING) analysis job.

    Compare-and-set: a terminal job is never overwritten, so a cancelled job
    cannot later become SUCCEEDED. Automatically handles timestamps for terminal
    states and running status; with no fields it only refreshes the heartbeat.

    Args:
        job_id (str): The unique identifier of the job.
        **fields: Keyword arguments representing the fields to update.

    Returns:
        bool: True if the job was still active and got updated.
    """
    if fields.get("status") in _JOB_TERMINAL:
        fields.setdefault("finished_at", datetime.now(timezone.utc))
    if fields.get("status") == "RUNNING":
        fields.setdefault("started_at", datetime.now(timezone.utc))
    fields.setdefault("heartbeat_at", datetime.now(timezone.utc))
    with _get_session() as s:
        n = (s.query(AnalysisJob)
               .filter(AnalysisJob.job_id == job_id, AnalysisJob.status.in_(_JOB_ACTIVE))
               .update({k: v for k, v in fields.items()}, synchronize_session=False))
        s.commit()
        return n > 0


def append_checkpoint(job_id: str, *, stage: str, agent: str,
                      message: str, state: str, pct: int) -> None:
    """Append a progress checkpoint to an active job's checkpoint log.

    Terminal jobs are left untouched, so write a final checkpoint before the
    terminal status.

    Args:
        job_id (str): The unique identifier of the job.
        stage (str): The current stage of the job.
        agent (str): The name of the agent or component reporting.
        message (str): A descriptive message for the checkpoint.
        state (str): The state of the checkpoint.
        pct (int): The current progress percentage (0-100).
    """
    # ponytail: row lock (no-op on SQLite) around a JSON read-modify-write; move to
    # a child table if checkpoint volume grows.
    with _get_session() as s:
        j = (s.query(AnalysisJob).filter(AnalysisJob.job_id == job_id)
               .with_for_update().first())
        if not j or j.status not in _JOB_ACTIVE:
            return
        cps = json.loads(j.checkpoints or "[]")
        cps.append({"ts": datetime.now(timezone.utc).isoformat(), "stage": stage,
                    "agent": agent, "message": message, "state": state})
        j.checkpoints = json.dumps(cps, ensure_ascii=False)
        j.stage = stage
        j.progress_pct = max(j.progress_pct or 0, int(pct))
        j.heartbeat_at = datetime.now(timezone.utc)
        s.commit()


def add_job_tokens(job_id: str, n: int) -> int:
    """Add tokens to the job's total token usage.

    Args:
        job_id (str): The unique identifier of the job.
        n (int): The number of tokens used to add.

    Returns:
        int: The updated total number of tokens used.
    """
    with _get_session() as s:
        j = s.get(AnalysisJob, job_id)
        if not j:
            return 0
        j.tokens_used = (j.tokens_used or 0) + int(n)
        j.heartbeat_at = datetime.now(timezone.utc)
        s.commit()
        return j.tokens_used


def get_active_job_for_user(user_id: Optional[int]) -> Optional[dict]:
    """Retrieve the most recent active job for a user.

    Rows older than any worker's wall-clock budget are ignored: their worker is
    dead, so they must not drive the app's "analysis running" indicator.

    Args:
        user_id (Optional[int]): ID of the user.

    Returns:
        Optional[dict]: A dictionary representation of the active job, or None.
    """
    if user_id is None:
        return None
    threshold = datetime.now(timezone.utc) - timedelta(seconds=_stale_after_sec())
    with _get_session() as s:
        j = (s.query(AnalysisJob)
               .filter(AnalysisJob.user_id == user_id,
                        AnalysisJob.status.in_(["QUEUED", "RUNNING"]),
                        AnalysisJob.created_at >= threshold)
               .order_by(AnalysisJob.created_at.desc()).first())
        return _job_to_dict(j) if j else None


def get_active_job_for_user_and_type(user_id: Optional[int], scan_type: str) -> Optional[dict]:
    """Active (QUEUED/RUNNING) job for this user AND scan_type, ignoring stale
    jobs older than their wall-clock limit. Lets extreme and standard coexist."""
    if user_id is None:
        return None
    threshold = datetime.now(timezone.utc) - timedelta(seconds=_stale_after_sec(scan_type))
    with _get_session() as s:
        j = (s.query(AnalysisJob)
               .filter(AnalysisJob.user_id == user_id,
                        AnalysisJob.scan_type == scan_type,
                        AnalysisJob.status.in_(["QUEUED", "RUNNING"]),
                        AnalysisJob.created_at >= threshold)
               .order_by(AnalysisJob.created_at.desc()).first())
        return _job_to_dict(j) if j else None


def list_active_jobs() -> list[dict]:
    """All QUEUED/RUNNING jobs — for the live dashboard 'what's running' panel."""
    with _get_session() as s:
        rows = (s.query(AnalysisJob)
                  .filter(AnalysisJob.status.in_(["QUEUED", "RUNNING"]))
                  .order_by(AnalysisJob.created_at.desc()).all())
        return [_job_to_dict(j) for j in rows]


def list_jobs_for_user_and_type(
    user_id: int,
    scan_type: str,
    *,
    limit: int = 50,
) -> list[dict]:
    """Newest jobs for one user and engine type."""
    with _get_session() as s:
        rows = (
            s.query(AnalysisJob)
            .filter(
                AnalysisJob.user_id == user_id,
                AnalysisJob.scan_type == scan_type,
            )
            .order_by(AnalysisJob.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_job_to_dict(j) for j in rows]


def list_monitor_jobs(
    *,
    mode: str = "running",
    ticker: Optional[str] = None,
    limit: int = 20,
    stuck_minutes: int = 15,
    now: Optional[datetime] = None,
) -> list[dict]:
    """Job rows for the AI engine monitor, matching scripts/check_jobs.py modes."""
    normalized_mode = (mode or "running").strip()
    normalized_ticker = (ticker or "").strip().upper()
    if not normalized_ticker and normalized_mode not in {"running", "all", "--all", "stuck", "--stuck"}:
        normalized_ticker = normalized_mode.upper()

    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=stuck_minutes)
    if cutoff.tzinfo is not None:
        cutoff = cutoff.replace(tzinfo=None)

    with _get_session() as s:
        query = s.query(AnalysisJob)
        query_limit: Optional[int] = None
        if normalized_ticker:
            query = query.filter(AnalysisJob.ticker == normalized_ticker)
            query_limit = min(limit, 5)
        elif normalized_mode == "running":
            query = query.filter(AnalysisJob.status == "RUNNING")
        elif normalized_mode in {"stuck", "--stuck"}:
            query = query.filter(
                AnalysisJob.status == "RUNNING",
                AnalysisJob.created_at < cutoff,
            )
        elif normalized_mode in {"all", "--all"}:
            query_limit = limit
        else:
            query = query.filter(AnalysisJob.ticker == normalized_mode.upper())
            query_limit = min(limit, 5)

        query = query.order_by(AnalysisJob.created_at.desc())
        if query_limit is not None:
            query = query.limit(query_limit)
        rows = query.all()
        return [_job_to_monitor_dict(j) for j in rows]


def get_monitor_job(job_id: str) -> Optional[dict]:
    """Single job row with raw result JSON for monitor detail views."""
    with _get_session() as s:
        j = s.get(AnalysisJob, job_id)
        return _job_to_monitor_dict(j) if j else None


def get_latest_successful_monitor_job(ticker: str) -> Optional[dict]:
    """Latest successful analysis for a ticker, matching scripts/show_result.py."""
    with _get_session() as s:
        j = (s.query(AnalysisJob)
               .filter(AnalysisJob.ticker == ticker.upper(),
                       AnalysisJob.status == "SUCCEEDED")
               .order_by(AnalysisJob.created_at.desc())
               .first())
        return _job_to_monitor_dict(j) if j else None


def _pid_alive(pid: Optional[int]) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True  # exists, owned by another user
    except OSError:
        return False
    return True


def sweep_stale_jobs(max_heartbeat_age_sec: int = 90) -> int:
    """Crash recovery: mark QUEUED/RUNNING jobs whose worker is gone as FAILED.

    A stale heartbeat counts only when the worker pid is not alive on this host.
    A row past every wall-clock budget (plus margin) is failed regardless of pid,
    so a reused pid cannot keep a dead row RUNNING; a still-live overrun worker
    sees the terminal status on its next heartbeat and exits.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=max_heartbeat_age_sec)
    overrun_before = now - timedelta(seconds=max(WALLCLOCK_LIMITS.values()) + 120)
    gone = or_(AnalysisJob.heartbeat_at < cutoff, AnalysisJob.created_at < overrun_before)
    with _get_session() as s:
        stale = (s.query(AnalysisJob.job_id, AnalysisJob.pid)
                   .filter(AnalysisJob.status.in_(_JOB_ACTIVE), gone).all())
        if not stale:
            return 0
        overrun = {row[0] for row in
                   s.query(AnalysisJob.job_id)
                    .filter(AnalysisJob.status.in_(_JOB_ACTIVE),
                            AnalysisJob.created_at < overrun_before).all()}
        dead = [jid for jid, pid in stale if jid in overrun or not _pid_alive(pid)]
        if not dead:
            return 0
        n = (s.query(AnalysisJob)
               .filter(AnalysisJob.job_id.in_(dead),
                       AnalysisJob.status.in_(_JOB_ACTIVE), gone)
               .update({"status": "FAILED", "finished_at": now,
                        "error": "Worker died (stale heartbeat / server restart)"},
                       synchronize_session=False))
        s.commit()
        return n
