"""
Concurrency limiter for AI operations — per-user semaphores and
running-analysis slot tracking with staleness auto-cleanup.
Extracted from helpers.py.
"""
import threading
import time

_analyze_semaphores: dict[int, threading.Semaphore] = {}
_analyze_sem_lock = threading.Lock()
_ANALYZE_MAX_CONCURRENT = 2

def _get_analyze_semaphore(user_id: int) -> threading.Semaphore:
    with _analyze_sem_lock:
        if user_id not in _analyze_semaphores:
            _analyze_semaphores[user_id] = threading.Semaphore(_ANALYZE_MAX_CONCURRENT)
        return _analyze_semaphores[user_id]

# Running analyses tracker — user_id → start_timestamp
# Protected by _running_lock. Entries older than STALENESS_TIMEOUT_SEC
# are auto-cleared on next acquire attempt (prevents permanent lockout after
# server crash, OOM kill, or worker hang that bypasses the finally block).
_RUNNING_ANALYSES_STALENESS_SEC = 600  # 10 minutes — analysis should never take longer
_running_analyses: dict[int, float] = {}  # user_id → time.time() when started
_running_lock = threading.Lock()

def _acquire_analysis_slot(user_id: int) -> bool:
    """Try to acquire an analysis slot for user_id. Returns True on success.
    Auto-clears stale entries older than STALENESS_TIMEOUT_SEC.
    Fix 2.32: Entire check-and-set atomic under _running_lock — no TOCTOU gap."""
    with _running_lock:
        now = time.time()
        # Purge stale entries
        stale = [uid for uid, ts in _running_analyses.items()
                 if now - ts > _RUNNING_ANALYSES_STALENESS_SEC]
        for uid in stale:
            _running_analyses.pop(uid, None)
            _release_analyze_semaphore(uid)

        if user_id in _running_analyses:
            return False
        _running_analyses[user_id] = now
        return True

def _release_analysis_slot(user_id: int) -> None:
    """Release the analysis slot for user_id."""
    with _running_lock:
        _running_analyses.pop(user_id, None)
    _release_analyze_semaphore(user_id)

def _force_clear_analysis_slot(user_id: int) -> bool:
    """Admin: force-clear a stuck analysis slot. Returns True if slot existed."""
    with _running_lock:
        if user_id in _running_analyses:
            _running_analyses.pop(user_id, None)
            _release_analyze_semaphore(user_id)
            return True
        return False

def _get_stuck_analyses() -> list[dict]:
    """Return list of currently stuck analysis slots with age info."""
    with _running_lock:
        now = time.time()
        return [{"user_id": uid, "running_sec": round(now - ts, 1),
                  "is_stale": (now - ts) > _RUNNING_ANALYSES_STALENESS_SEC}
                for uid, ts in _running_analyses.items()]

def _release_analyze_semaphore(user_id: int) -> None:
    """Release one permit from user's analysis semaphore if held."""
    sem = _get_analyze_semaphore(user_id)
    try:
        sem.release()
    except ValueError:
        pass  # Semaphore already at max — nothing to release
