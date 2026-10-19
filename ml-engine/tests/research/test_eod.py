"""Read-only EOD export and marketdata sync (``research/marketdata/eod.py``, ``/eod`` and ``/marketdata/sync``).

Nothing here touches the network; panels are small synthetic frames.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from research import api, config
from research.marketdata import bhavcopy, eod, store

KEY = "test-key-not-a-secret"
AUTH = {"X-ML-Engine-Key": KEY}
D = date(2026, 10, 9)
TODAY = date(2026, 10, 15)


def _row(d: date, symbol: str, source: str = "nse_bhavcopy", **kw: Any) -> dict[str, Any]:
    base = {
        "date": pd.Timestamp(d), "entity_id": f"E{symbol}", "isin": f"INE{symbol[:3]}A01018", "symbol": symbol,
        "open": 10.0, "high": 12.5, "low": 9.5, "close": 11.25, "prev_close": 10.5, "volume": 1000.0,
        "turnover_inr": 11250.0, "trades": 40.0, "px_idx": 11.25, "event": "", "quality_flags": "", "source": source,
    }
    base.update(kw)
    return base


def _panel(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=store.PANEL_COLUMNS)


def _loader(panel: pd.DataFrame):
    def load(start: date, end: date, source: str = "store", data_dir: Any = None) -> pd.DataFrame:
        mask = (panel["date"] >= pd.Timestamp(start)) & (panel["date"] <= pd.Timestamp(end))
        return panel.loc[mask].reset_index(drop=True)

    return load


def _index(d: date, value: float = 25000.5):
    def load(name: str, start: Any, end: Any, data_dir: Any = None) -> pd.Series:
        return pd.Series([value], index=pd.DatetimeIndex([pd.Timestamp(d)]))

    return load


def _no_index(name: str, start: Any, end: Any, data_dir: Any = None) -> None:
    return None


def test_exports_only_that_dates_bhavcopy_rows() -> None:
    panel = _panel([
        _row(D, "TCS", volume=np.nan, event="split"),
        _row(D, "INFY"),
        _row(D, "YFONLY", source="yfinance"),
        _row(D + timedelta(days=1), "TCS"),
    ])
    out = eod.eod_rows(D, today=TODAY, panel_loader=_loader(panel), index_loader=_index(D))
    assert out["status"] == "ok" and out["market_date"] == "2026-10-09"
    assert [r["symbol"] for r in out["rows"]] == ["INFY", "TCS"]
    tcs = out["rows"][1]
    assert tcs["volume"] is None and tcs["event"] == "split" and tcs["trades"] == 40
    assert isinstance(tcs["trades"], int) and tcs["close"] == 11.25 and tcs["quality_flags"] == ""
    assert set(tcs) == set(eod.EXPORT_COLUMNS)
    assert out["index_closes"] == {"NIFTY50": 25000.5}


def test_index_omitted_without_bar_for_the_date() -> None:
    panel = _panel([_row(D, "TCS"), _row(D + timedelta(days=1), "TCS")])
    assert eod.eod_rows(D, today=TODAY, panel_loader=_loader(panel), index_loader=_no_index)["index_closes"] == {}
    other = eod.eod_rows(D, today=TODAY, panel_loader=_loader(panel), index_loader=_index(D - timedelta(days=1)))
    assert other["index_closes"] == {}


def test_missing_date_with_later_rows_is_no_session_via_holiday_check() -> None:
    panel = _panel([_row(D + timedelta(days=2), "TCS")])
    out = eod.eod_rows(D, today=TODAY, panel_loader=_loader(panel), holiday_check=lambda d: True)
    assert out == {"market_date": "2026-10-09", "status": "no_session", "rows": [], "index_closes": {}}
    with pytest.raises(eod.NotIngested):
        eod.eod_rows(D, today=TODAY, panel_loader=_loader(panel), holiday_check=lambda d: False)


def test_no_later_rows_and_future_date_are_not_ingested() -> None:
    panel = _panel([_row(D - timedelta(days=3), "TCS")])
    with pytest.raises(eod.NotIngested):
        eod.eod_rows(D, today=TODAY, panel_loader=_loader(panel), holiday_check=lambda d: True)
    with pytest.raises(eod.NotIngested):
        eod.eod_rows(TODAY + timedelta(days=1), today=TODAY, panel_loader=_loader(panel))


def test_real_holiday_check_never_downloads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class Boom:
        def fetch(self, _d: date) -> None:
            raise AssertionError("eod_rows must never download")

    monkeypatch.setattr(store, "Downloader", Boom)
    panel = _panel([_row(D + timedelta(days=2), "TCS")])
    out = eod.eod_rows(D, data_dir=tmp_path, today=TODAY, panel_loader=_loader(panel))
    assert out["status"] == "no_session"


def test_real_holiday_check_with_stored_zip_is_not_ingested(tmp_path: Path) -> None:
    zip_path = tmp_path / store._zip_rel(D)
    zip_path.parent.mkdir(parents=True)
    zip_path.write_bytes(b"x")
    panel = _panel([_row(D + timedelta(days=2), "TCS")])
    with pytest.raises(eod.NotIngested):
        eod.eod_rows(D, data_dir=tmp_path, today=TODAY, panel_loader=_loader(panel))


class _Result:
    added = [D]
    no_session = [D - timedelta(days=1)]
    failed = {D - timedelta(days=2): "boom"}


def test_sync_reports_index_error_without_raising() -> None:
    def refresh(name: str, **kw: Any) -> int:
        raise RuntimeError("yahoo down")

    out = eod.sync_marketdata(D, ensure=lambda through, **kw: _Result(), refresh_index=refresh,
                              yf_factory=lambda: object())
    assert out["added"] == ["2026-10-09"] and out["no_session"] == ["2026-10-08"]
    assert out["failed"] == {"2026-10-07": "boom"} and out["index_error"].startswith("RuntimeError")
    ok = eod.sync_marketdata(D, ensure=lambda through, **kw: _Result(), refresh_index=lambda n, **kw: 1,
                             yf_factory=lambda: object())
    assert ok["index_error"] is None


def test_sync_propagates_schema_errors() -> None:
    def ensure(through: date, **kw: Any) -> None:
        raise bhavcopy.BhavcopySchemaError("columns changed")

    with pytest.raises(bhavcopy.BhavcopySchemaError):
        eod.sync_marketdata(D, ensure=ensure, refresh_index=lambda n, **kw: 1, yf_factory=lambda: object())


# ── routes ──────────────────────────────────────────────────────────────────


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[TestClient]:
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setenv("ML_ENGINE_API_KEY", KEY)
    monkeypatch.setattr(api, "_ACTIVE", None)
    monkeypatch.setattr(api, "_ist_today", lambda: TODAY)
    app = FastAPI()
    app.include_router(api.router)
    yield TestClient(app)
    active = api._ACTIVE
    if active is not None:
        active["thread"].join(timeout=10)


def test_eod_route_ok_and_not_ingested(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"market_date": "2026-10-09", "status": "ok", "rows": [], "index_closes": {}}
    monkeypatch.setattr(api.eod, "eod_rows", lambda d, data_dir=None: payload)
    resp = client.get("/research/v1/eod/2026-10-09", headers=AUTH)
    assert resp.status_code == 200 and resp.json() == payload

    def missing(d: date, data_dir: Any = None) -> None:
        raise eod.NotIngested("nope")

    monkeypatch.setattr(api.eod, "eod_rows", missing)
    resp = client.get("/research/v1/eod/2026-10-09", headers=AUTH)
    assert resp.status_code == 404 and resp.json() == {"code": "NOT_INGESTED"}


def test_eod_route_auth_and_validation(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    assert client.get("/research/v1/eod/2026-10-09").status_code == 401
    assert client.get("/research/v1/eod/2026-10-09", headers={"X-ML-Engine-Key": "wrong"}).status_code == 401
    assert client.get("/research/v1/eod/2026-13-40", headers=AUTH).status_code == 422
    monkeypatch.delenv("ML_ENGINE_API_KEY")
    assert client.get("/research/v1/eod/2026-10-09", headers=AUTH).status_code == 503


def test_sync_route_starts_and_reports_busy(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    done = threading.Event()
    calls: list[date] = []

    def fake_sync(through: date, data_dir: Any = None) -> dict[str, Any]:
        calls.append(through)
        done.set()
        return {}

    monkeypatch.setattr(api.eod, "sync_marketdata", fake_sync)
    resp = client.post("/research/v1/marketdata/sync", json={"through": "2026-10-14"}, headers=AUTH)
    assert resp.status_code == 202 and resp.json() == {"status": "started", "through": "2026-10-14"}
    assert done.wait(5) and calls == [date(2026, 10, 14)]
    api._ACTIVE["thread"].join(timeout=5) if api._ACTIVE else None


def test_sync_route_busy_and_future(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    assert client.post("/research/v1/marketdata/sync", json={"through": "2026-10-16"}, headers=AUTH).status_code == 422
    release = threading.Event()
    blocker = threading.Thread(target=release.wait, daemon=True)
    blocker.start()
    monkeypatch.setattr(api, "_ACTIVE", {"run_id": api._SYNC_ID, "market_date": None, "thread": blocker})
    resp = client.post("/research/v1/marketdata/sync", json={"through": "2026-10-14"}, headers=AUTH)
    assert resp.status_code == 409 and resp.json() == {"code": "ENGINE_BUSY"}
    # /runs answers its own 409 with a null market_date while a sync holds the slot.
    run = client.post("/research/v1/runs", json={"market_date": "2026-10-14"}, headers=AUTH)
    assert run.status_code == 409 and run.json() == {"run_id": api._SYNC_ID, "market_date": None}
    assert _lock_held_check(client)
    release.set()
    blocker.join(timeout=5)


def _lock_held_check(client: TestClient) -> bool:
    assert api._LOCK.acquire(blocking=False)
    try:
        resp = client.post("/research/v1/marketdata/sync", json={"through": "2026-10-14"}, headers=AUTH)
        return resp.status_code == 409
    finally:
        api._LOCK.release()


def test_sync_route_validation_and_auth(client: TestClient) -> None:
    assert client.post("/research/v1/marketdata/sync", json={"through": "2026-13-40"}, headers=AUTH).status_code == 422
    assert client.post("/research/v1/marketdata/sync", json={"through": "2026-10-14"}).status_code == 401
