"""
Dashboard state — shared mutable state used by middleware, admin endpoints,
and harvest workers. Protected by _dash_lock.

Extracted from helpers.py.
"""
import os
import json
import threading
import uuid
from datetime import datetime, timezone
from collections import deque

_dash_lock = threading.Lock()
_harvest_status = {
    "advisor":  {"status": "idle", "last_run": None, "last_result": None},
    "youtube":  {"status": "idle", "last_run": None, "last_result": None},
    "news":     {"status": "idle", "last_run": None, "last_result": None},
    "filings":  {"status": "idle", "last_run": None, "last_result": None},
}
_active_analyses: dict = {}
_completed_analyses: deque = deque(maxlen=200)
_request_log: deque = deque(maxlen=500)
_dash_logs: deque = deque(maxlen=200)
_token_stats = {
    "total_input": 0,
    "total_output": 0,
    "total_cache_read": 0,
    "total_cache_write": 0,
    "total_calls": 0,
    "recent": deque(maxlen=50),
}
_token_log_lock = threading.Lock()
TOKEN_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "token_log.jsonl")


def _dash_update_harvest(key: str, status: str, result: dict | None = None) -> None:
    with _dash_lock:
        if key in _harvest_status:
            _harvest_status[key]["status"] = status
            if status == "running":
                _harvest_status[key]["last_run"] = datetime.now(timezone.utc).isoformat()
            if result is not None:
                _harvest_status[key]["last_result"] = result
                _dash_logs.appendleft({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "key": key,
                    "status": status,
                    "result": result
                })

def _dash_start_job(job_id: str, ticker: str, exchange: str, user_id) -> None:
    with _dash_lock:
        _active_analyses[job_id] = {
            "job_id": job_id,
            "ticker": ticker.upper(),
            "exchange": exchange,
            "user_id": user_id,
            "start_ts": datetime.now(timezone.utc).isoformat(),
            "stage": "AI agents initializing...",
        }

def _dash_end_job(job_id: str, result: dict | None = None, error: str | None = None, killed: bool = False) -> None:
    with _dash_lock:
        job = _active_analyses.pop(job_id, None)
        if not job:
            return
        duration = (datetime.now(timezone.utc) - datetime.fromisoformat(job["start_ts"])).total_seconds()
        entry = {**job, "end_ts": datetime.now(timezone.utc).isoformat(), "duration_s": round(duration, 1)}
        if result:
            entry["signal"] = result.get("signal")
            entry["confidence"] = result.get("confidence_pct")
            entry["company_name"] = result.get("company_name", "")
            entry["cache_type"] = result.get("_cache_type", "FULL AI")
            entry["status"] = "completed"
        elif killed:
            entry["status"] = "disconnected"
            entry["cache_type"] = "\u2014"
        else:
            entry["status"] = "error"
            entry["error"] = error or "unknown"
            entry["cache_type"] = "\u2014"
        _completed_analyses.appendleft(entry)

def _dash_log_request(method: str, path: str, params: dict, status: int, duration_ms: float) -> None:
    with _dash_lock:
        _request_log.appendleft({
            "id": str(uuid.uuid4())[:8],
            "ts": datetime.now(timezone.utc).isoformat(),
            "method": method,
            "path": path,
            "params": params,
            "status": status,
            "duration_ms": round(duration_ms),
        })

def _log_token_usage(endpoint: str, usage) -> None:
    inp = getattr(usage, "input_tokens", 0)
    if inp == 0:
        inp = getattr(usage, "prompt_tokens", 0)
    out = getattr(usage, "output_tokens", 0)
    if out == 0:
        out = getattr(usage, "completion_tokens", 0)
    cr = getattr(usage, "cache_read_input_tokens", 0)
    cw = getattr(usage, "cache_creation_input_tokens", 0)
    try:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "input_tokens": inp,
            "output_tokens": out,
            "cache_creation_input_tokens": cw,
            "cache_read_input_tokens": cr,
        }
        with _token_log_lock:
            with open(TOKEN_LOG_PATH, "a") as f:
                f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
    with _dash_lock:
        _token_stats["total_input"]      += inp
        _token_stats["total_output"]     += out
        _token_stats["total_cache_read"] += cr
        _token_stats["total_cache_write"]+= cw
        _token_stats["total_calls"]      += 1
        _token_stats["recent"].appendleft({
            "ts": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "input": inp,
            "output": out,
        })
