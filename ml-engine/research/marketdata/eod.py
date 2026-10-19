"""Read-only end-of-day export for the backend's Postgres mirror (data foundation, I15).

``eod_rows`` reads the curated store only: it takes no lock, never downloads and
never writes. ``sync_marketdata`` is the engine's own gap-fill (``ensure_sessions``
plus ``refresh_index``), started by ``POST /marketdata/sync`` under the run lock.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from research.marketdata import store

log = logging.getLogger(__name__)

EXPORT_COLUMNS = [
    "symbol", "isin", "entity_id", "open", "high", "low", "close", "prev_close",
    "volume", "turnover_inr", "trades", "event", "quality_flags",
]
_INT_COLUMNS = ("volume", "trades")
_LOOKAHEAD_DAYS = 10


class NotIngested(Exception):
    """The store has not (yet) ingested this date."""


def _no_fetch(_d: date) -> None:
    """The only fetch this module ever passes: it reports 'nothing to download'."""
    return None


def _ist_today() -> date:
    from research import pipeline

    return datetime.now(pipeline.IST).date()


def _cell(column: str, value: Any) -> Any:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    if column in _INT_COLUMNS:
        return int(value)
    if column in ("symbol", "isin", "entity_id", "event", "quality_flags"):
        return str(value)
    return float(value)


def eod_rows(
    market_date: date,
    *,
    data_dir: str | Path | None = None,
    today: date | None = None,
    panel_loader: Callable[..., pd.DataFrame] = store.load_panel,
    index_loader: Callable[..., pd.Series | None] = store.load_index,
    holiday_check: Callable[[date], bool] | None = None,
) -> dict[str, Any]:
    """The bhavcopy EQ rows of ``market_date``; raises ``NotIngested`` while the store has not moved past it."""
    today = today or _ist_today()
    if market_date > today:
        raise NotIngested(f"{market_date} is in the future")
    panel = panel_loader(market_date, market_date + timedelta(days=_LOOKAHEAD_DAYS), source="store",
                         data_dir=data_dir)
    bhav = panel[panel["source"] == "nse_bhavcopy"]
    day = bhav[bhav["date"].dt.date == market_date]
    if len(day):
        day = day.sort_values("symbol", kind="stable")
        rows = [{c: _cell(c, v) for c, v in zip(EXPORT_COLUMNS, rec)}
                for rec in day[EXPORT_COLUMNS].itertuples(index=False, name=None)]
        index_closes: dict[str, float] = {}
        idx = index_loader("NIFTY50", market_date, market_date, data_dir=data_dir)
        if idx is not None and len(idx) and idx.index[-1].date() == market_date:
            index_closes["NIFTY50"] = float(idx.iloc[-1])
        return {"market_date": market_date.isoformat(), "status": "ok", "rows": rows,
                "index_closes": index_closes}
    if not bool((bhav["date"].dt.date > market_date).any()):
        raise NotIngested(f"the store has no bhavcopy after {market_date}")
    check = holiday_check or (lambda d: store.is_holiday(d, data_dir=data_dir, fetch=_no_fetch))
    if check(market_date):
        return {"market_date": market_date.isoformat(), "status": "no_session", "rows": [], "index_closes": {}}
    raise NotIngested(f"{market_date} is not a holiday but has no bhavcopy yet")


def sync_marketdata(
    through: date,
    *,
    data_dir: str | Path | None = None,
    ensure: Callable[..., Any] = store.ensure_sessions,
    refresh_index: Callable[..., Any] = store.refresh_index,
    yf_factory: Callable[[], Any] = store.YFinance,
) -> dict[str, Any]:
    """The research run's gap-fill (15-day window, throttled honest-UA downloader), then the Nifty 50 cache."""
    yf = yf_factory()
    result = ensure(through, data_dir=data_dir, yf=yf)  # BhavcopySchemaError propagates
    index_error: str | None = None
    try:
        refresh_index("NIFTY50", data_dir=data_dir, yf=yf)
    except Exception as exc:
        log.warning("marketdata sync: index refresh failed: %s", exc)
        index_error = f"{type(exc).__name__}: {exc}"[:300]
    return {
        "through": through.isoformat(),
        "added": [d.isoformat() for d in result.added],
        "no_session": [d.isoformat() for d in result.no_session],
        "failed": {d.isoformat(): msg for d, msg in result.failed.items()},
        "index_error": index_error,
    }
