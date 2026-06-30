"""
nivesh.subprocess_runner — Subprocess Isolation & Concurrency Throttling (Task 13.4)
======================================================================================
Wraps heavy graph-propagation work inside ``multiprocessing.Process`` to prevent
resource-intensive LangGraph runs from blocking FastAPI's async event loop.

Architecture
------------
    FastAPI async handler
        └── run_analysis_isolated()           ← non-blocking, awaits completion
              └── multiprocessing.Process
                    └── _worker()             ← subprocess: imports TradingAgentsGraph,
                                                 runs propagate(), puts result in Queue

Concurrency Guard
-----------------
``_running_analyses: set[int]`` is an in-process set tracking user IDs that have
an active analysis subprocess. A user who triggers a second analysis while one is
already running receives an immediate 429-style ``AnalysisAlreadyRunningError``
without spawning a new subprocess.

This guard is intentionally in-process (not Redis/DB) — it is fast, zero-latency,
and sufficient for single-process FastAPI deployments. Multi-process deployments
(e.g. gunicorn workers) must use an external lock (Redis SET NX) instead; this
module documents that limitation clearly.

Public API
----------
    from tradingagents.nivesh.subprocess_runner import (
        run_analysis_isolated,
        AnalysisAlreadyRunningError,
    )

    try:
        result = run_analysis_isolated(
            ticker="SUZLON.NS",
            trade_date="2026-06-03",
            user_id=42,
            config_overrides={"max_debate_rounds": 1},
            timeout_seconds=300,
        )
    except AnalysisAlreadyRunningError:
        # return 429 to client
        ...
"""

from __future__ import annotations

import logging
import multiprocessing
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-user concurrency guard
# NOTE: single-process guarantee only. See module docstring for multi-worker.
# ---------------------------------------------------------------------------
_running_analyses: set[int] = set()
_running_lock = threading.Lock()


class AnalysisAlreadyRunningError(RuntimeError):
    """Raised when a user already has an active analysis subprocess."""


# ---------------------------------------------------------------------------
# Subprocess worker — runs inside a fresh multiprocessing.Process
# ---------------------------------------------------------------------------

def _worker(
    queue: multiprocessing.Queue,
    ticker: str,
    trade_date: str,
    config_overrides: dict[str, Any],
) -> None:
    """Entry point executed inside the child process.

    Imports are deferred to this function so the parent process does not
    pay the import cost of LangGraph / LangChain for every call site that
    merely imports this module.
    """
    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG

        config = {**DEFAULT_CONFIG, **config_overrides}
        graph = TradingAgentsGraph(
            selected_analysts=config_overrides.get(
                "selected_analysts", ["governance", "market", "news", "fundamentals"]
            ),
            config=config,
        )
        final_state, decision = graph.propagate(ticker, trade_date)
        queue.put(
            {
                "status": "ok",
                "final_trade_decision": final_state.get("final_trade_decision", ""),
                "decision": decision,
                "market_report": final_state.get("market_report", ""),
                "news_report": final_state.get("news_report", ""),
                "fundamentals_report": final_state.get("fundamentals_report", ""),
                "sentiment_report": final_state.get("sentiment_report", ""),
                "governance_report": final_state.get("governance_report", ""),
                "investment_plan": final_state.get("investment_plan", ""),
                "trader_investment_plan": final_state.get("trader_investment_plan", ""),
            }
        )
    except Exception as exc:
        queue.put({"status": "error", "error": str(exc)})


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def run_analysis_isolated(
    ticker: str,
    trade_date: str,
    user_id: int | None = None,
    config_overrides: dict[str, Any] | None = None,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Run a TradingAgentsGraph propagation in an isolated subprocess.

    Parameters
    ----------
    ticker:
        Full ticker symbol, e.g. ``"SUZLON.NS"``.
    trade_date:
        Analysis date string ``"YYYY-MM-DD"``.
    user_id:
        Optional integer user identifier. When provided, the per-user
        concurrency guard is enforced — a second call for the same user
        raises ``AnalysisAlreadyRunningError`` immediately.
    config_overrides:
        Dict merged over ``DEFAULT_CONFIG`` before constructing the graph.
        Useful for setting ``max_debate_rounds``, ``llm_provider``, etc.
    timeout_seconds:
        How long to wait for the subprocess before raising ``TimeoutError``.
        Default 300 s (5 minutes).

    Returns
    -------
    dict
        ``{"status": "ok", "final_trade_decision": ..., "decision": ..., ...}``

    Raises
    ------
    AnalysisAlreadyRunningError
        If ``user_id`` already has an active analysis.
    TimeoutError
        If the subprocess does not complete within ``timeout_seconds``.
    RuntimeError
        If the subprocess itself raises an unhandled exception.
    """
    if user_id is not None:
        with _running_lock:
            if user_id in _running_analyses:
                raise AnalysisAlreadyRunningError(
                    f"Analysis already running for user_id={user_id}. Please wait."
                )
            _running_analyses.add(user_id)

    queue: multiprocessing.Queue = multiprocessing.Queue()
    process = multiprocessing.Process(
        target=_worker,
        args=(queue, ticker, trade_date, config_overrides or {}),
        daemon=True,
    )

    try:
        process.start()
        logger.info(
            "[subprocess_runner] Started PID=%d for ticker=%s user_id=%s",
            process.pid,
            ticker,
            user_id,
        )

        deadline = time.monotonic() + timeout_seconds
        result: dict[str, Any] | None = None

        while time.monotonic() < deadline:
            if not queue.empty():
                result = queue.get_nowait()
                break
            if not process.is_alive():
                # Process exited without putting anything in queue
                if not queue.empty():
                    result = queue.get_nowait()
                break
            time.sleep(0.5)

        if result is None:
            process.terminate()
            process.join(timeout=5)
            raise TimeoutError(
                f"[subprocess_runner] Analysis for {ticker} timed out after "
                f"{timeout_seconds}s"
            )

        if result.get("status") == "error":
            raise RuntimeError(
                f"[subprocess_runner] Worker failed for {ticker}: {result.get('error')}"
            )

        return result

    finally:
        if user_id is not None:
            with _running_lock:
                _running_analyses.discard(user_id)
        # Ensure the process is cleaned up
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)


def is_analysis_running(user_id: int) -> bool:
    """Return True if ``user_id`` has an active analysis subprocess."""
    with _running_lock:
        return user_id in _running_analyses


def get_running_user_ids() -> frozenset[int]:
    """Return a snapshot of user IDs currently running an analysis."""
    with _running_lock:
        return frozenset(_running_analyses)
