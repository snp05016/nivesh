"""HTTP client for the ml-engine research API (spec 9.2, ``/research/v1``).

Synchronous (scheduler jobs are plain ``def``; async callers use a thread).
Timeouts: 10 s default, 15 s for ``/compute``, 2 s for ``/ready``. A timeout,
connection error or 5xx raises ``MLEngineUnavailable``; any other unexpected
status raises ``MLEngineError``. Logs carry the endpoint and status only, never
the ``X-ML-Engine-Key`` value.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, NamedTuple, Optional

import httpx

from . import config

logger = logging.getLogger(__name__)

PREFIX = "/research/v1"
DEFAULT_TIMEOUT = 10.0
COMPUTE_TIMEOUT = 15.0
READY_TIMEOUT = 2.0
ITEMS_PAGE = 200


class MLEngineError(Exception):
    """ml-engine answered with a status the caller did not expect."""

    def __init__(self, endpoint: str, status_code: Optional[int], detail: str = "") -> None:
        super().__init__(f"ml-engine {endpoint}: {status_code if status_code is not None else detail}")
        self.endpoint = endpoint
        self.status_code = status_code


class MLEngineUnavailable(MLEngineError):
    """Timeout, connection failure or 5xx."""


class EngineResponse(NamedTuple):
    status_code: int
    body: dict[str, Any]


class MLEngineClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        *,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        cfg = config.CONFIG
        self.base_url = (base_url or cfg.ml_engine_url).rstrip("/")
        self._api_key = api_key if api_key is not None else cfg.ml_engine_api_key
        self._transport = transport  # tests inject httpx.MockTransport

    def __repr__(self) -> str:  # never show the key
        return f"MLEngineClient({self.base_url!r})"

    # -- transport ---------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        ok: tuple[int, ...],
        timeout: float = DEFAULT_TIMEOUT,
        json: Any = None,
        params: Optional[dict[str, Any]] = None,
    ) -> EngineResponse:
        endpoint = f"{method} {PREFIX}{path}"
        headers = {"X-ML-Engine-Key": self._api_key} if self._api_key else {}
        try:
            with httpx.Client(timeout=timeout, transport=self._transport) as http:
                resp = http.request(method, f"{self.base_url}{PREFIX}{path}", json=json, params=params, headers=headers)
        except httpx.HTTPError as exc:  # timeouts, refused connections, protocol errors
            logger.warning("ml-engine %s unreachable: %s", endpoint, type(exc).__name__)
            raise MLEngineUnavailable(endpoint, None, type(exc).__name__) from None
        if resp.status_code >= 500 and resp.status_code not in ok:
            logger.warning("ml-engine %s returned %d", endpoint, resp.status_code)
            raise MLEngineUnavailable(endpoint, resp.status_code)
        if resp.status_code not in ok:
            logger.warning("ml-engine %s returned %d", endpoint, resp.status_code)
            raise MLEngineError(endpoint, resp.status_code)
        try:
            body = resp.json()
        except ValueError:
            logger.warning("ml-engine %s returned non-JSON (%d)", endpoint, resp.status_code)
            raise MLEngineError(endpoint, resp.status_code, "non-JSON body") from None
        if not isinstance(body, dict):
            raise MLEngineError(endpoint, resp.status_code, "body is not an object")
        return EngineResponse(resp.status_code, body)

    # -- endpoints ---------------------------------------------------------

    def start_run(self, market_date: date, extra_symbols: list[str]) -> EngineResponse:
        """POST /runs. 202 running, 200 skipped_holiday or an existing run,
        409 ``{run_id, market_date}`` while another run is active (returned,
        not raised)."""
        return self._request(
            "POST", "/runs", ok=(200, 202, 409),
            json={"market_date": market_date.isoformat(), "extra_symbols": list(extra_symbols)},
        )

    def run_status(self, run_id: str) -> Optional[dict[str, Any]]:
        """RunStatus, or None when ml-engine has no such run (404)."""
        resp = self._request("GET", f"/runs/{run_id}", ok=(200, 404))
        return None if resp.status_code == 404 else resp.body

    def run_items(self, run_id: str) -> list[dict[str, Any]]:
        """Every RunItem of a finished run, paging ``/items`` 200 at a time."""
        items: list[dict[str, Any]] = []
        offset: Optional[int] = 0
        while offset is not None:
            body = self._request(
                "GET", f"/runs/{run_id}/items", ok=(200,), params={"offset": offset, "limit": ITEMS_PAGE},
            ).body
            items.extend(body.get("items") or [])
            nxt = body.get("next_offset")
            offset = int(nxt) if nxt is not None and int(nxt) > offset else None
        return items

    def compute(self, symbol: str) -> EngineResponse:
        """POST /compute (15 s). 200 ``{report}``, 404 ``UNKNOWN_SYMBOL`` and
        422 (insufficient history) are returned; 5xx raises."""
        return self._request("POST", "/compute", ok=(200, 404, 422), timeout=COMPUTE_TIMEOUT, json={"symbol": symbol})

    def outcomes(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """POST /outcomes (<= 5,000 items) -> ``{results, last_session}``."""
        return self._request("POST", "/outcomes", ok=(200,), json={"items": items}).body

    def live_metrics(self, request: dict[str, Any]) -> dict[str, Any]:
        """POST /live-metrics: LiveMetricsRequest -> LiveMetricsResponse."""
        return self._request("POST", "/live-metrics", ok=(200,), json=request).body

    def model_card(self) -> dict[str, Any]:
        return self._request("GET", "/model-card", ok=(200,)).body

    def ready(self) -> dict[str, Any]:
        """``{"ready": bool, "reasons": [...]}`` within 2 s. Never raises: an
        unreachable engine reads as not ready (``ml_engine_unreachable``)."""
        try:
            body = self._request("GET", "/ready", ok=(200, 503), timeout=READY_TIMEOUT).body
        except MLEngineError:
            return {"ready": False, "reasons": ["ml_engine_unreachable"]}
        return {**body, "ready": bool(body.get("ready")), "reasons": list(body.get("reasons") or [])}
