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

SERVER_START = datetime.now(timezone.utc)
_dash_lock = threading.Lock()
_harvest_status = {
    "advisor":  {"status": "idle", "last_run": None, "last_result": None},
    "youtube":  {"status": "idle", "last_run": None, "last_result": None},
    "news":     {"status": "idle", "last_run": None, "last_result": None},
    "filings":  {"status": "idle", "last_run": None, "last_result": None},
    "research_nightly": {"status": "idle", "last_run": None, "last_result": None},
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

# USD per 1M tokens (input, output). First substring match on the lower-cased model wins,
# so the more specific 'deepseek-reasoner' must precede 'deepseek'.
_PRICING_PER_M: list[tuple[str, float, float]] = [
    ("deepseek-reasoner", 0.55, 2.19),
    ("deepseek", 0.14, 0.28),
    ("haiku", 1.0, 5.0),
    ("sonnet", 3.0, 15.0),
    ("opus", 15.0, 75.0),
]


def estimate_cost_usd(model: str | None, input_tokens: int, output_tokens: int) -> float | None:
    """USD cost of one call, or None when the model is missing or unpriced."""
    m = (model or "").lower()
    for needle, in_rate, out_rate in _PRICING_PER_M:
        if needle in m:
            return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000
    return None


def model_vendor(model: str | None) -> str:
    """'deepseek', 'claude' or 'unknown' — the dashboard cost bucket for a model."""
    m = (model or "").lower()
    if "deepseek" in m:
        return "deepseek"
    if any(k in m for k in ("haiku", "sonnet", "opus")):
        return "claude"
    return "unknown"


def _dash_update_harvest(key: str, status: str, result: dict | None = None) -> None:
    with _dash_lock:
        # Scheduler jobs (bhavcopy, rag_ingest, ...) register themselves on first update.
        _harvest_status.setdefault(key, {"status": "idle", "last_run": None, "last_result": None})
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

_LOG_FIELD_MAX = 200


def _dash_log_request(method: str, path: str, params: dict, status: int, duration_ms: float) -> None:
    # Paths/params are attacker-controlled (404s included): cap their size before they sit in memory (AUTH-19).
    capped = {str(k)[:_LOG_FIELD_MAX]: str(v)[:_LOG_FIELD_MAX] for k, v in list(params.items())[:20]}
    with _dash_lock:
        _request_log.appendleft({
            "id": str(uuid.uuid4())[:8],
            "ts": datetime.now(timezone.utc).isoformat(),
            "method": method,
            "path": path[:_LOG_FIELD_MAX],
            "params": capped,
            "status": status,
            "duration_ms": round(duration_ms),
        })

def _log_token_usage(endpoint: str, usage, model: str | None = None) -> None:
    """Record one LLM call. Pass `model` so the dashboard can price it by vendor."""
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
            "model": model or "unknown",
            "input_tokens": inp,
            "output_tokens": out,
            "cache_creation_input_tokens": cw,
            "cache_read_input_tokens": cr,
        }
        with _token_log_lock:
            with open(TOKEN_LOG_PATH, "a") as f:
                f.write(json.dumps(entry) + "\n")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to log token usage: {e}")
    with _dash_lock:
        _token_stats["total_input"]      += inp
        _token_stats["total_output"]     += out
        _token_stats["total_cache_read"] += cr
        _token_stats["total_cache_write"]+= cw
        _token_stats["total_calls"]      += 1
        _token_stats["recent"].appendleft({
            "ts": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "model": model or "unknown",
            "input": inp,
            "output": out,
            "cache_read": cr,
            "cache_write": cw,
        })
