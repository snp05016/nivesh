"""AnalysisJob DAO — query functions extracted from database.py."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from models.db_models import AnalysisJob


def _get_session():
    """Lazy import to avoid circular dependency with database module."""
    from database import get_session
    return get_session()


_JOB_TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED", "TIMEOUT"}

# Wall-clock limits mirror services.job_worker._WALLCLOCK_LIMITS so a crashed
# worker never permanently blocks new runs of the same scan_type.
_STALE_LIMITS: dict[str, int] = {"extreme": 600, "deep": 420, "standard": 300}


def _job_to_dict(j: "AnalysisJob") -> dict:
    return {
        "job_id": j.job_id, "user_id": j.user_id, "ticker": j.ticker,
        "exchange": j.exchange, "scan_type": j.scan_type, "status": j.status,
        "stage": j.stage, "progress_pct": j.progress_pct,
        "checkpoints": json.loads(j.checkpoints or "[]"),
        "pid": j.pid, "tokens_used": j.tokens_used, "error": j.error,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "finished_at": j.finished_at.isoformat() if j.finished_at else None,
    }


def create_job(user_id: Optional[int], ticker: str, exchange: str, scan_type: str) -> dict:
    jid = str(uuid.uuid4())[:12]
    with _get_session() as s:
        j = AnalysisJob(job_id=jid, user_id=user_id, ticker=ticker.upper(),
                        exchange=exchange, scan_type=scan_type, status="QUEUED",
                        heartbeat_at=datetime.utcnow())
        s.add(j)
        s.commit()
        return _job_to_dict(j)


def get_job(job_id: str) -> Optional[dict]:
    with _get_session() as s:
        j = s.get(AnalysisJob, job_id)
        if not j:
            return None
        d = _job_to_dict(j)
        if j.status == "SUCCEEDED" and j.result_json:
            try:
                d["result"] = json.loads(j.result_json)
            except Exception:
                d["result"] = None
        return d


def update_job(job_id: str, **fields) -> None:
    if fields.get("status") in _JOB_TERMINAL:
        fields.setdefault("finished_at", datetime.utcnow())
    if fields.get("status") == "RUNNING":
        fields.setdefault("started_at", datetime.utcnow())
    fields.setdefault("heartbeat_at", datetime.utcnow())
    with _get_session() as s:
        j = s.get(AnalysisJob, job_id)
        if not j:
            return
        for k, v in fields.items():
            setattr(j, k, v)
        s.commit()


def append_checkpoint(job_id: str, *, stage: str, agent: str,
                      message: str, state: str, pct: int) -> None:
    with _get_session() as s:
        j = s.get(AnalysisJob, job_id)
        if not j:
            return
        cps = json.loads(j.checkpoints or "[]")
        cps.append({"ts": datetime.utcnow().isoformat(), "stage": stage,
                    "agent": agent, "message": message, "state": state})
        j.checkpoints = json.dumps(cps, ensure_ascii=False)
        j.stage = stage
        j.progress_pct = max(j.progress_pct or 0, int(pct))
        j.heartbeat_at = datetime.utcnow()
        s.commit()


def add_job_tokens(job_id: str, n: int) -> int:
    with _get_session() as s:
        j = s.get(AnalysisJob, job_id)
        if not j:
            return 0
        j.tokens_used = (j.tokens_used or 0) + int(n)
        j.heartbeat_at = datetime.utcnow()
        s.commit()
        return j.tokens_used


def get_active_job_for_user(user_id: Optional[int]) -> Optional[dict]:
    if user_id is None:
        return None
    with _get_session() as s:
        j = (s.query(AnalysisJob)
               .filter(AnalysisJob.user_id == user_id,
                        AnalysisJob.status.in_(["QUEUED", "RUNNING"]))
               .order_by(AnalysisJob.created_at.desc()).first())
        return _job_to_dict(j) if j else None


def get_active_job_for_user_and_type(user_id: Optional[int], scan_type: str) -> Optional[dict]:
    """Active (QUEUED/RUNNING) job for this user AND scan_type, ignoring stale
    jobs older than their wall-clock limit. Lets extreme and standard coexist."""
    if user_id is None:
        return None
    cutoff_sec = _STALE_LIMITS.get(scan_type, 300)
    threshold = datetime.utcnow() - timedelta(seconds=cutoff_sec)
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


def sweep_stale_jobs(max_heartbeat_age_sec: int = 90) -> int:
    """Crash recovery: mark QUEUED/RUNNING jobs with a stale heartbeat as FAILED."""
    cutoff = datetime.utcnow() - timedelta(seconds=max_heartbeat_age_sec)
    with _get_session() as s:
        stale = (s.query(AnalysisJob)
                   .filter(AnalysisJob.status.in_(["QUEUED", "RUNNING"]),
                            AnalysisJob.heartbeat_at < cutoff).all())
        for j in stale:
            j.status = "FAILED"
            j.error = "Worker died (stale heartbeat / server restart)"
            j.finished_at = datetime.utcnow()
        s.commit()
        return len(stale)
