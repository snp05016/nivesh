import logging
"""Job-scoped checkpoint emitter — the single channel for per-agent progress.

Each agent node calls ``emit(...)`` to record a one-line status + progress %.
Safe no-op when ``job_id`` is None (e.g. standard scans not tracked as jobs, or
direct library use outside a job context). Never raises into the analysis pipeline.
"""
from __future__ import annotations


class CheckpointEmitter:
    def __init__(self, job_id: str | None):
        self.job_id = job_id

    def emit(self, stage: str, agent: str, message: str, *,
             pct: int, state: str = "running") -> None:
        if not self.job_id:
            return
        try:
            import database
            database.append_checkpoint(
                self.job_id, stage=stage, agent=agent,
                message=message, state=state, pct=pct,
            )
        except Exception as e:  # progress must never break the analysis
            logging.info(f"[checkpoint] emit failed for job {self.job_id}: {e}")
