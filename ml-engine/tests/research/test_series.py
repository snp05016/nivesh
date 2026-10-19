"""Series routes (package money-ml-series): window returns sharing the /outcomes rule, and raw highs.

Synthetic panels only; store reads are replaced by in-memory frames. No network.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from research import api, config, series
from research.contract import OutcomeRequestItem
from research.marketdata import store, universe
from research.outcomes import score_outcomes
from research.report import as_timestamp

N_NAMES = 45
N_SESSIONS = 160
TODAY = date(2025, 9, 30)
KEY = "test-key-not-a-secret"


def _panel(seed: int = 7, start: str = "2025-01-01") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(start, periods=N_SESSIONS)
    frames = []
    for i in range(N_NAMES):
        close = 100.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, N_SESSIONS)))
        frames.append(pd.DataFrame({
            "date": days, "entity_id": f"S{i:02d}", "isin": f"INE{i:06d}01", "symbol": f"S{i:02d}",
            "open": close, "high": close * 1.01, "low": close * 0.99, "close": close,
            "prev_close": np.r_[np.nan, close[:-1]], "volume": 1e5, "turnover_inr": close * 1e5,
            "trades": np.nan, "px_idx": close / close[0], "event": "", "quality_flags": "", "source": "local_csv",
        }))
    return pd.concat(frames, ignore_index=True).sort_values(["entity_id", "date"]).reset_index(drop=True)


def _entities(panel: pd.DataFrame) -> pd.DataFrame:
    g = panel.groupby("entity_id").agg(isin=("isin", "first"), symbol=("symbol", "first"),
                                       valid_from=("date", "min"), valid_to=("date", "max")).reset_index()
    g["link_reason"] = "test"
    return g


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    panel = _panel()
    cal = store.sessions(panel)
    index = pd.Series(np.linspace(100.0, 140.0, N_SESSIONS), index=cal)
    state: dict[str, Any] = {"panel": panel, "calls": [], "index": index}

    def load_panel(start: Any = None, end: Any = None, source: str = "store", data_dir: Any = None) -> pd.DataFrame:
        state["calls"].append((start, end))
        p = state["panel"]
        mask = pd.Series(True, index=p.index)
        if start is not None:
            mask &= p["date"] >= pd.Timestamp(start)
        if end is not None:
            mask &= p["date"] <= pd.Timestamp(end)
        return p.loc[mask].reset_index(drop=True)

    monkeypatch.setattr(store, "load_panel", load_panel)
    monkeypatch.setattr(store, "load_entities", lambda data_dir=None: _entities(state["panel"]))
    monkeypatch.setattr(store, "load_index", lambda name="NIFTY50", start=None, end=None, data_dir=None: state["index"])
    state["cal"] = cal
    return state


def _item(key: str, sym: str, start: date, sessions: int = 21, **kw: Any) -> dict[str, Any]:
    return {"key": key, "symbol": sym, "isin": None, "start": start, "sessions": sessions, **kw}


def _res(world: dict[str, Any], items: list[dict[str, Any]], today: date = TODAY) -> dict[str, Any]:
    return series.window_returns(items, today=today)


def test_matches_score_outcomes(world: dict[str, Any]) -> None:
    panel, cal = world["panel"], world["cal"]
    t = as_timestamp(cal[20])
    close = float(panel.loc[(panel["symbol"] == "S05") & (panel["date"] == t), "close"].iloc[0])
    expected = score_outcomes(
        [OutcomeRequestItem.model_validate({"prediction_id": 1, "isin": None, "symbol": "S05", "as_of": t.date(),
                                            "horizon_days": 21, "entry_close": close})],
        panel, universe.membership(panel), world["index"], data_dir=Path("."),
    )[0]
    got = _res(world, [_item("a", "S05", t.date())])["results"][0]
    assert got["status"] == "ok"
    assert got["return_pct"] == pytest.approx(expected.realized_return_pct)
    assert got["stale_exit"] == expected.stale_exit
    assert got["nifty_return_pct"] == pytest.approx(expected.nifty50_return_pct)
    assert got["end_date"] == as_timestamp(cal[41]).date().isoformat()


def test_sessions_follow_store_calendar(world: dict[str, Any]) -> None:
    cal = world["cal"]
    # Remove one business day from every name: the 21st session is the next real one.
    holiday = cal[30]
    world["panel"] = world["panel"].loc[world["panel"]["date"] != holiday].reset_index(drop=True)
    cal2 = store.sessions(world["panel"])
    got = _res(world, [_item("a", "S01", as_timestamp(cal2[20]).date())])["results"][0]
    assert got["end_date"] == as_timestamp(cal2[41]).date().isoformat()


def test_start_on_non_session_uses_previous_session(world: dict[str, Any]) -> None:
    cal = world["cal"]
    saturday = as_timestamp(cal[20]).date()
    while saturday.weekday() != 5:
        saturday = date.fromordinal(saturday.toordinal() + 1)
    got = _res(world, [_item("a", "S02", saturday)])["results"][0]
    assert got["status"] == "ok"
    assert pd.Timestamp(got["start_date"]).weekday() == 4


def test_split_day_keeps_px_idx_continuous(world: dict[str, Any]) -> None:
    p = world["panel"]
    cal = world["cal"]
    mask = (p["symbol"] == "S03") & (p["date"] >= cal[25])
    p.loc[mask, ["open", "high", "low", "close"]] = p.loc[mask, ["open", "high", "low", "close"]] / 5.0  # raw prices drop
    got = _res(world, [_item("a", "S03", as_timestamp(cal[20]).date())])["results"][0]
    px = p.loc[p["symbol"] == "S03"].set_index("date")["px_idx"]
    assert got["return_pct"] == pytest.approx((px[cal[41]] / px[cal[20]] - 1.0) * 100.0)


def test_zero_volume_nan_day_is_skipped(world: dict[str, Any]) -> None:
    p, cal = world["panel"], world["cal"]
    bad = (p["symbol"] == "S04") & (p["date"] == cal[41])
    p.loc[bad, ["volume", "px_idx"]] = [0.0, np.nan]
    got = _res(world, [_item("a", "S04", as_timestamp(cal[20]).date())])["results"][0]
    px = p.loc[(p["symbol"] == "S04") & (p["date"] == cal[40])]["px_idx"].iloc[0]
    start = p.loc[(p["symbol"] == "S04") & (p["date"] == cal[20])]["px_idx"].iloc[0]
    assert got["status"] == "ok"
    assert got["return_pct"] == pytest.approx((px / start - 1.0) * 100.0)


def test_early_stop_is_stale_exit(world: dict[str, Any]) -> None:
    p, cal = world["panel"], world["cal"]
    world["panel"] = p.loc[~((p["symbol"] == "S06") & (p["date"] > cal[25]))].reset_index(drop=True)
    got = _res(world, [_item("a", "S06", as_timestamp(cal[20]).date())])["results"][0]
    assert got["status"] == "ok" and got["stale_exit"] is True


def test_start_before_listing_is_no_data(world: dict[str, Any]) -> None:
    p, cal = world["panel"], world["cal"]
    world["panel"] = p.loc[~((p["symbol"] == "S07") & (p["date"] < cal[60]))].reset_index(drop=True)
    got = _res(world, [_item("a", "S07", as_timestamp(cal[20]).date())])["results"][0]
    assert got["status"] == "no_data"


def test_unknown_symbol(world: dict[str, Any]) -> None:
    got = _res(world, [_item("a", "NOPE", date(2025, 3, 3))])["results"][0]
    assert got["status"] == "unknown_symbol" and got["return_pct"] is None


def test_isin_lookup(world: dict[str, Any]) -> None:
    got = _res(world, [{"key": "a", "symbol": None, "isin": "INE000008" + "01", "start": as_timestamp(world["cal"][20]).date(), "sessions": 21}])["results"][0]
    assert got["status"] == "ok"


def test_window_past_last_session_is_pending(world: dict[str, Any]) -> None:
    cal = world["cal"]
    got = _res(world, [_item("a", "S01", as_timestamp(cal[-5]).date())], today=date(2025, 8, 14))
    assert got["results"][0]["status"] == "pending"
    assert got["last_session"] == as_timestamp(cal[-1]).date().isoformat()


def test_two_items_years_apart_load_two_bounded_panels(world: dict[str, Any]) -> None:
    far = _panel(seed=9, start="2022-01-03")
    world["panel"] = pd.concat([far, world["panel"]], ignore_index=True)
    world["panel"] = world["panel"].sort_values(["entity_id", "date"]).reset_index(drop=True)
    world["calls"].clear()
    out = _res(world, [_item("old", "S01", date(2022, 2, 1)), _item("new", "S01", date(2025, 2, 3))])
    assert [r["status"] for r in out["results"]] == ["ok", "ok"]
    span_calls = [c for c in world["calls"] if c[1] != TODAY]
    bounded = [c for c in world["calls"] if c[0] is not None and c[1] is not None]
    assert len(world["calls"]) == len(bounded) == 3  # two spans plus the last-session probe
    spans = sorted(c for c in span_calls if (pd.Timestamp(c[1]) - pd.Timestamp(c[0])).days > 11)
    assert len(spans) == 2
    assert all((pd.Timestamp(b) - pd.Timestamp(a)).days < 120 for a, b in spans)


def test_raw_highs_previous_trade_when_date_has_none(world: dict[str, Any]) -> None:
    p, cal = world["panel"], world["cal"]
    target = as_timestamp(cal[30])
    world["panel"] = p.loc[~((p["symbol"] == "S08") & (p["date"] == target))].reset_index(drop=True)
    out = series.raw_highs([{"key": "h", "symbol": "S08", "isin": None, "date": target.date()}])["results"][0]
    prev = world["panel"].loc[(world["panel"]["symbol"] == "S08") & (world["panel"]["date"] == cal[29])].iloc[0]
    assert out["status"] == "ok"
    assert out["date_used"] == as_timestamp(cal[29]).date().isoformat()
    assert out["high"] == pytest.approx(float(prev["high"]))
    assert out["close"] == pytest.approx(float(prev["close"]))


def test_raw_highs_skips_zero_volume_and_reports_no_trade(world: dict[str, Any]) -> None:
    p, cal = world["panel"], world["cal"]
    p.loc[(p["symbol"] == "S09") & (p["date"] == cal[30]), "volume"] = 0.0
    got = series.raw_highs([{"key": "h", "symbol": "S09", "isin": None, "date": as_timestamp(cal[30]).date()}])["results"][0]
    assert got["date_used"] == as_timestamp(cal[29]).date().isoformat()
    first = as_timestamp(cal[0]).date()
    none = series.raw_highs([{"key": "n", "symbol": "S09", "isin": None, "date": date.fromordinal(first.toordinal() - 60)}])["results"][0]
    assert none["status"] == "no_trade"
    unk = series.raw_highs([{"key": "u", "symbol": "NOPE", "isin": None, "date": first}])["results"][0]
    assert unk["status"] == "unknown_symbol"


# ── API ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, world: dict[str, Any]) -> Iterator[TestClient]:
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setenv("ML_ENGINE_API_KEY", KEY)
    app = FastAPI()
    app.include_router(api.router)
    with TestClient(app) as c:
        yield c


BODY = {"items": [{"key": "j1:21", "symbol": "S01", "start": "2025-02-03", "sessions": 21}]}


def test_api_auth(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    assert client.post("/research/v1/series/window-returns", json=BODY).status_code == 401
    assert client.post("/research/v1/series/window-returns", json=BODY, headers={"X-ML-Engine-Key": "wrong"}).status_code == 401
    monkeypatch.delenv("ML_ENGINE_API_KEY")
    assert client.post("/research/v1/series/raw-high", json={"items": []}, headers={"X-ML-Engine-Key": KEY}).status_code == 503


def test_api_validation(client: TestClient) -> None:
    h = {"X-ML-Engine-Key": KEY}
    url = "/research/v1/series/window-returns"
    both = {"items": [{"key": "k", "symbol": "S01", "isin": "INE000001012", "start": "2025-02-03", "sessions": 21}]}
    neither = {"items": [{"key": "k", "start": "2025-02-03", "sessions": 21}]}
    assert client.post(url, json=both, headers=h).status_code == 422
    assert client.post(url, json=neither, headers=h).status_code == 422
    for sessions in (0, 253):
        bad = {"items": [{"key": "k", "symbol": "S01", "start": "2025-02-03", "sessions": sessions}]}
        assert client.post(url, json=bad, headers=h).status_code == 422
    big = {"items": [{"key": f"k{i}", "symbol": "S01", "start": "2025-02-03", "sessions": 21} for i in range(2001)]}
    assert client.post(url, json=big, headers=h).status_code == 422


def test_api_shapes(client: TestClient) -> None:
    h = {"X-ML-Engine-Key": KEY}
    r = client.post("/research/v1/series/window-returns", json=BODY, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"results", "last_session"}
    assert set(body["results"][0]) == {"key", "status", "start_date", "end_date", "return_pct", "nifty_return_pct", "stale_exit"}
    r = client.post("/research/v1/series/raw-high", headers=h,
                    json={"items": [{"key": "h", "symbol": "S01", "date": "2025-02-03"}]})
    assert r.status_code == 200
    assert set(r.json()["results"][0]) == {"key", "status", "date_used", "high", "close"}
