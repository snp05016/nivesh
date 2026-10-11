"""
Dashboard state — shared mutable state used by middleware, admin endpoints,
and harvest workers. Protected by _dash_lock.

Extracted from helpers.py.
"""
import os
import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque

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
# Prompt-cache tokens, as multiples of the model's input rate: reads bill at 0.1x
# (Anthropic and DeepSeek cache hits), Anthropic 5-minute cache writes at 1.25x.
_CACHE_READ_MULT = 0.1
_CACHE_WRITE_MULT = 1.25
_IST = timezone(timedelta(hours=5, minutes=30))


def estimate_cost_usd(model: str | None, input_tokens: int, output_tokens: int,
                      cache_read_tokens: int = 0, cache_write_tokens: int = 0) -> float | None:
    """USD cost of one call, or None when the model is missing or unpriced."""
    m = (model or "").lower()
    for needle, in_rate, out_rate in _PRICING_PER_M:
        if needle in m:
            billed_input = (input_tokens + cache_read_tokens * _CACHE_READ_MULT
                            + cache_write_tokens * _CACHE_WRITE_MULT)
            return (billed_input * in_rate + output_tokens * out_rate) / 1_000_000
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

def _usage_int(usage, *names: str) -> int:
    """First non-zero integer token count among `names` (SDKs may report None)."""
    for name in names:
        v = getattr(usage, name, 0)
        if isinstance(v, int) and not isinstance(v, bool) and v:
            return v
    return 0


def _log_token_usage(endpoint: str, usage, model: str | None = None) -> None:
    """Record one LLM call. Pass `model` so the dashboard can price it by vendor."""
    inp = _usage_int(usage, "input_tokens", "prompt_tokens")
    out = _usage_int(usage, "output_tokens", "completion_tokens")
    cr = _usage_int(usage, "cache_read_input_tokens")
    cw = _usage_int(usage, "cache_creation_input_tokens")
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


def token_usage_summary() -> dict:
    """Aggregate token_log.jsonl into the admin spend view (LLM-09).

    The one reader of the log for /token-stats and /dashboard-data. Calls are priced per
    model including prompt-cache tokens; lines without a known model are counted in
    unpriced_calls and never guessed. Days are IST calendar days.
    """
    vendors = {
        "claude":   {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
        "deepseek": {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
        "unknown":  {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": None},
    }
    total_cost = 0.0
    calls = unpriced = 0
    tok_in = tok_out = tok_cr = tok_cw = 0
    by_endpoint: dict = defaultdict(float)
    by_model: dict = defaultdict(float)
    day_cost: dict = defaultdict(float)
    day_calls: dict = defaultdict(int)
    try:
        with open(TOKEN_LOG_PATH, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []
    except OSError as e:
        import logging
        logging.getLogger(__name__).warning(f"token log unreadable: {e}")
        lines = []

    for line in lines:
        try:
            e = json.loads(line)
            inp = int(e.get("input_tokens") or 0)
            out = int(e.get("output_tokens") or 0)
            cr = int(e.get("cache_read_input_tokens") or 0)
            cw = int(e.get("cache_creation_input_tokens") or 0)
        except (ValueError, TypeError, AttributeError):
            continue  # corrupt line, or not a JSON object
        model = e.get("model")
        cost = estimate_cost_usd(model, inp, out, cr, cw)
        bucket = vendors[model_vendor(model)]
        bucket["calls"] += 1
        bucket["input_tokens"] += inp
        bucket["output_tokens"] += out
        if cost is None:
            unpriced += 1
            cost = 0.0
        elif bucket["cost_usd"] is not None:
            bucket["cost_usd"] += cost
        calls += 1
        tok_in, tok_out, tok_cr, tok_cw = tok_in + inp, tok_out + out, tok_cr + cr, tok_cw + cw
        total_cost += cost
        by_endpoint[e.get("endpoint") or "unknown"] += cost
        by_model[model or "unknown"] += cost
        try:
            day = datetime.fromisoformat(e.get("ts") or "").astimezone(_IST).date().isoformat()
        except (TypeError, ValueError):
            continue
        day_cost[day] += cost
        day_calls[day] += 1

    usd_inr = float(os.getenv("USD_INR_RATE") or 88.0)
    last_7 = sorted(day_cost, reverse=True)[:7]
    return {
        "total_cost_usd": round(total_cost, 6),
        "total_cost_inr": round(total_cost * usd_inr, 2),
        "total_calls": calls,
        "unpriced_calls": unpriced,
        "cost_by_endpoint": {k: round(v, 6) for k, v in sorted(by_endpoint.items(), key=lambda x: x[1], reverse=True)},
        "cost_by_model": {k: round(v, 6) for k, v in sorted(by_model.items(), key=lambda x: x[1], reverse=True)},
        "by_vendor": vendors,
        # Share of prompt tokens served from cache (can never exceed 100%).
        "cache_hit_rate_pct": round(tok_cr / (tok_in + tok_cr) * 100, 2) if tok_in + tok_cr else 0.0,
        "most_expensive_endpoint": max(by_endpoint, key=lambda k: by_endpoint[k]) if by_endpoint else None,
        "total_input_tokens": tok_in,
        "total_output_tokens": tok_out,
        "total_cache_read_tokens": tok_cr,
        "total_cache_write_tokens": tok_cw,
        "estimated_monthly_usd": round(sum(day_cost.values()) / len(day_cost) * 30, 2) if day_cost else 0.0,
        "last_7_days": [{"date": d, "calls": day_calls[d], "cost_usd": round(day_cost[d], 6)} for d in last_7],
    }
