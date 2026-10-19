"""HTTP client for the ml-engine Lab API (``/lab/v1``, docs/platform/api-contract.md).

Base URL and ``X-ML-Engine-Key`` come from the research config (``ML_ENGINE_URL``,
``ML_ENGINE_API_KEY``), read at call time. A 404 or 422 from the engine is passed
through as a ``LabError`` with the engine's detail (e.g. ``"action 3: ..."``); a
timeout, connection error or any other status is a 503 with a fixed message, and
logs carry the endpoint and status only, never the key or the engine's error text.
Callers (and tests) use the module-level functions below.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from services.research import config as research_config

from . import LabError

logger = logging.getLogger(__name__)

PREFIX = "/lab/v1"
DEFAULT_TIMEOUT = 10.0
SIM_TIMEOUT = 30.0
RESEARCH_TIMEOUT = 180.0  # permutation tests over the panel
RETRY_AFTER = "30"
UNAVAILABLE = {"code": "LAB_ENGINE_UNAVAILABLE", "message": "The Lab engine is unavailable. Please retry shortly."}
_REJECTED = "The Lab engine rejected the request."


def _unavailable() -> LabError:
    return LabError(503, UNAVAILABLE, headers={"Retry-After": RETRY_AFTER})


def _detail(resp: httpx.Response) -> Any:
    try:
        detail = resp.json().get("detail")
    except (ValueError, AttributeError):
        return _REJECTED
    return detail if isinstance(detail, (str, list)) and detail else _REJECTED


def _call(method: str, path: str, *, json: Any = None, params: Optional[dict] = None,
          timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    cfg = research_config.CONFIG
    endpoint = f"{method} {PREFIX}{path}"
    headers = {"X-ML-Engine-Key": cfg.ml_engine_api_key} if cfg.ml_engine_api_key else {}
    try:
        with httpx.Client(timeout=timeout) as http:
            resp = http.request(method, f"{cfg.ml_engine_url}{PREFIX}{path}", json=json, params=params, headers=headers)
    except httpx.HTTPError as exc:
        logger.warning("ml-engine %s unreachable: %s", endpoint, type(exc).__name__)
        raise _unavailable() from None
    if resp.status_code in (404, 422):
        raise LabError(resp.status_code, _detail(resp))
    if resp.status_code != 200:
        logger.warning("ml-engine %s returned %d", endpoint, resp.status_code)
        raise _unavailable()
    try:
        body = resp.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        logger.warning("ml-engine %s returned a non-object body", endpoint)
        raise _unavailable()
    return body


# -- Time Machine ------------------------------------------------------------

def sim_state(config: dict, actions: list[dict]) -> dict:
    return _call("POST", "/sim/state", json={"config": config, "actions": actions}, timeout=SIM_TIMEOUT)


def sim_history(config: dict, asof: str, symbol: str, bars: int) -> dict:
    return _call("POST", "/sim/history", json={"config": config, "asof": asof, "symbol": symbol, "bars": bars},
                 timeout=SIM_TIMEOUT)


def sim_autopsy(config: dict, actions: list[dict], order_id: Optional[str] = None) -> dict:
    return _call("POST", "/sim/autopsy", json={"config": config, "actions": actions, "order_id": order_id},
                 timeout=SIM_TIMEOUT)


def scenarios() -> dict:
    return _call("GET", "/scenarios")


def universe(start: str, n: int) -> dict:
    return _call("GET", "/universe", params={"start": start, "n": n}, timeout=SIM_TIMEOUT)


def events_timeline(symbol: str, start: str, end: str) -> dict:
    return _call("POST", "/events/timeline", json={"symbol": symbol, "start": start, "end": end}, timeout=SIM_TIMEOUT)


# -- Research ----------------------------------------------------------------

def templates() -> dict:
    return _call("GET", "/hypothesis/templates")


def compile_program(program: str) -> dict:
    return _call("POST", "/features/compile", json={"program": program})


def run_hypothesis(spec: dict) -> dict:
    return _call("POST", "/hypothesis/run", json=spec, timeout=RESEARCH_TIMEOUT)


def compare(body: dict) -> dict:
    return _call("POST", "/hypothesis/compare", json=body, timeout=RESEARCH_TIMEOUT)


def sweep(body: dict) -> dict:
    return _call("POST", "/hypothesis/sweep", json=body, timeout=RESEARCH_TIMEOUT)


# -- School ------------------------------------------------------------------

def curriculum() -> dict:
    return _call("GET", "/school/curriculum")


def lesson(lesson_id: str) -> dict:
    return _call("GET", f"/school/lessons/{lesson_id}")


def grade(lesson_id: str, answers: list[int], state: dict) -> dict:
    return _call("POST", "/school/grade", json={"lesson_id": lesson_id, "answers": answers, "state": state})


def next_lessons(state: dict, weaknesses: list[str], k: int) -> dict:
    return _call("POST", "/school/next", json={"state": state, "weaknesses": weaknesses, "k": k})
