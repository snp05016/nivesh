"""services/eod_prices.py: the Postgres mirror of the ml-engine export and the display-gated accessors. Hermetic."""
import importlib.util
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from models.db_models import DailyPrice, Instrument, InstrumentAlias, MutualFund
from services import eod_prices, instruments
from services.research import config as research_config
from services.research.client import MLEngineUnavailable
from tests.data_db import patch_get_session

D = date(2026, 10, 9)
NOW = datetime(2026, 10, 12, 17, 0, tzinfo=timezone.utc)  # 22:30 IST, Monday: last_due = 2026-10-12


@pytest.fixture
def factory(monkeypatch):
    f = patch_get_session(monkeypatch)
    monkeypatch.setattr(eod_prices, "MIN_ROWS", 5)
    return f


@pytest.fixture
def db(factory):
    with factory() as s:
        yield s


def _row(i, symbol=None, close=100.0, **kw):
    isin = f"INE{i:07d}01"
    row = {"symbol": symbol or f"S{i:04d}", "isin": isin, "entity_id": f"E{isin}", "open": 99.5, "high": 101.25,
           "low": 98.0, "close": close, "prev_close": 99.0, "volume": 1000, "turnover_inr": 100000.0,
           "trades": 12, "event": "", "quality_flags": ""}
    row.update(kw)
    return row


def _payload(rows, index=None, status="ok"):
    return {"market_date": "x", "status": status, "rows": rows, "index_closes": index or {}}


class FakeClient:
    def __init__(self, by_date=None, fail_on=None):
        self.by_date = by_date or {}
        self.fail_on = fail_on
        self.syncs = []

    def eod(self, d):
        if self.fail_on == d:
            raise MLEngineUnavailable("GET /eod", 503)
        return self.by_date.get(d)

    def marketdata_sync(self, through):
        self.syncs.append(through)
        return "started"


def _cfg(monkeypatch, mode="off", key="k"):
    monkeypatch.setattr(research_config, "CONFIG", replace(research_config.CONFIG, mode=mode, ml_engine_api_key=key))


def test_mirror_writes_rows_index_and_instruments(db):
    rows = [_row(i) for i in range(1200)]
    rows[0]["event"] = "split"
    rows[1]["close"] = None
    client = FakeClient({D: _payload(rows, {"NIFTY50": 25123.45})})
    assert eod_prices.mirror_date(D, client=client) == 1199
    assert db.query(DailyPrice).filter_by(source="nse_bhavcopy").count() == 1199
    assert db.query(Instrument).filter_by(asset_class="EQ").count() == 1199
    first = db.query(Instrument).filter_by(symbol="S0000").one()
    price = db.query(DailyPrice).filter_by(instrument_id=first.id).one()
    assert price.event == "split" and price.close == Decimal("100.0000") and price.quality_flags is None
    idx = db.query(DailyPrice).join(Instrument).filter(Instrument.asset_class == "INDEX").one()
    assert idx.close == Decimal("25123.4500") and idx.source == "yfinance"


def test_rerun_is_idempotent(db):
    client = FakeClient({D: _payload([_row(i) for i in range(1200)], {"NIFTY50": 25000.0})})
    assert eod_prices.mirror_date(D, client=client) == 1200
    assert eod_prices.mirror_date(D, client=client) == 1200
    assert db.query(DailyPrice).count() == 1201
    assert db.query(Instrument).count() == 1201
    assert db.query(InstrumentAlias).count() == 0


def test_nothing_written_for_none_no_session_or_short_payload(db, monkeypatch):
    monkeypatch.setattr(eod_prices, "MIN_ROWS", 1000)
    for payload in (None, _payload([], status="no_session"), _payload([_row(i) for i in range(999)])):
        assert eod_prices.mirror_date(D, client=FakeClient({D: payload})) == 0
    assert db.query(DailyPrice).count() == 0 and db.query(Instrument).count() == 0


def test_rename_mid_window_keeps_one_alias_and_reruns_cleanly(db, monkeypatch):
    _cfg(monkeypatch, mode="shadow")
    by_date = {}
    for day in range(1, 11):
        sym = "OLD" if day <= 4 else "NEW"
        by_date[date(2026, 10, day)] = _payload([_row(i, symbol=sym if i == 0 else None) for i in range(6)])
    client = FakeClient(by_date)
    first = eod_prices.mirror_recent(client=client, now=NOW)
    assert first["dates_written"] == 10 and first["sync"] == "skipped:research_runs"
    inst = db.query(Instrument).filter_by(entity_id="EINE000000001").one()
    assert inst.symbol == "NEW"
    assert [(a.kind, a.value) for a in db.query(InstrumentAlias).filter_by(instrument_id=inst.id)] == [("symbol", "OLD")]
    again = eod_prices.mirror_recent(client=client, now=NOW)
    assert again["dates_written"] == 10
    db.expire_all()
    assert db.query(InstrumentAlias).count() == 1
    assert db.query(Instrument).filter_by(entity_id="EINE000000001").one().symbol == "NEW"


def test_mirror_recent_skips(monkeypatch, db):
    monkeypatch.setenv("FEATURE_DATA_EOD_PRICES", "false")
    assert eod_prices.mirror_recent(client=FakeClient(), now=NOW) == {"skipped": "flag_off"}
    monkeypatch.delenv("FEATURE_DATA_EOD_PRICES")
    _cfg(monkeypatch, key=None)
    assert eod_prices.mirror_recent(client=FakeClient(), now=NOW) == {"skipped": "ml_engine_unconfigured"}


def test_sync_only_when_research_mode_off(monkeypatch, db):
    _cfg(monkeypatch, mode="off")
    client = FakeClient()
    out = eod_prices.mirror_recent(client=client, now=NOW)
    assert client.syncs == [date(2026, 10, 12)] and out["sync"] == "started"
    _cfg(monkeypatch, mode="on")
    client = FakeClient()
    eod_prices.mirror_recent(client=client, now=NOW)
    assert client.syncs == []


def test_mirror_recent_stops_when_engine_unavailable(monkeypatch, db):
    _cfg(monkeypatch, mode="shadow")
    by_date = {date(2026, 10, d): _payload([_row(i) for i in range(6)]) for d in (1, 2, 3)}
    out = eod_prices.mirror_recent(client=FakeClient(by_date, fail_on=date(2026, 10, 4)), now=NOW)
    assert out == {"error": "ml_engine_unavailable", "sync": "skipped:research_runs", "dates_written": 3}


def test_last_due_before_and_after_930_pm_ist():
    # 15:00 UTC = 20:30 IST (before 21:30): the previous weekday of Monday is Friday
    assert eod_prices._last_due(datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)) == date(2026, 10, 9)
    assert eod_prices._last_due(datetime(2026, 10, 12, 16, 30, tzinfo=timezone.utc)) == date(2026, 10, 12)


def _seed(db, symbol="ABC", isin="INE111A01011", closes=None, flags=None, asset_class="EQ", **kw):
    inst = Instrument(asset_class=asset_class, symbol=symbol, isin=isin, name=symbol or "x", source="t",
                      status="active", last_seen_on=D, **kw)
    db.add(inst)
    db.flush()
    for d, close in (closes or {}).items():
        db.add(DailyPrice(instrument_id=inst.id, trade_date=d, close=close, source="nse_bhavcopy",
                          quality_flags=(flags or {}).get(d), ingested_at=datetime(2026, 10, 9)))
    db.commit()
    return inst


def test_get_close_gating_age_suspect_and_alias(db, monkeypatch):
    _seed(db, closes={date(2026, 10, 9): 110, date(2026, 10, 8): 105, date(2026, 9, 1): 90},
          flags={date(2026, 10, 9): "suspect_tick"})
    on = date(2026, 10, 12)
    assert eod_prices.get_close("ABC", on=on) is None  # display flag off
    fact = eod_prices.get_close("ABC", on=on, for_display=False)
    assert fact.close == Decimal("105") and fact.trade_date == date(2026, 10, 8) and fact.source == "nse_bhavcopy"
    assert eod_prices.get_close("ABC", on=date(2026, 10, 30), for_display=False) is None
    assert eod_prices.get_close("ABC", on=date(2026, 10, 30), max_age_days=30, for_display=False).close == Decimal("105")
    monkeypatch.setenv("FEATURE_DATA_EOD_DISPLAY", "true")
    assert eod_prices.get_close(isin="INE111A01011", on=on).close == Decimal("105")
    # a renamed symbol resolves through its alias
    inst = db.query(Instrument).filter_by(symbol="ABC").one()
    instruments.upsert_eq_identity(db, symbol="XYZ", isin="INE111A01011", seen_on=D, source="t")
    db.commit()
    assert eod_prices.get_close("abc.ns", on=on).instrument_id == inst.id


def test_index_close_is_display_gated(db, monkeypatch):
    _seed(db, symbol="NIFTY50", isin=None, asset_class="INDEX", closes={date(2026, 10, 9): 25000})
    on = date(2026, 10, 12)
    assert eod_prices.index_close(on=on) is None
    assert eod_prices.index_close(on=on, for_display=False).close == Decimal("25000")


def test_mf_always_served_with_nav_fallback(db):
    on = date(2026, 10, 12)
    _seed(db, symbol=None, isin="INF000A01011", asset_class="MF", amfi_scheme_code="100", closes={date(2026, 10, 9): 52.5})
    _seed(db, symbol=None, isin="INF000B01011", asset_class="MF", amfi_scheme_code="200")
    db.add(MutualFund(fund_name="B", amc="x", category="Equity", scheme_code="200", nav=33.25, nav_date="2026-10-10"))
    db.commit()
    assert eod_prices.get_close(isin="INF000A01011", on=on).close == Decimal("52.5")
    fallback = eod_prices.get_close(isin="INF000B01011", on=on)
    assert fallback.close == Decimal("33.25") and fallback.source == "amfi_latest"
    assert eod_prices.get_close(isin="INF000B01011", on=on, for_display=False).source == "amfi_latest"


def test_get_closes_symbol_and_isin_together(db, monkeypatch):
    monkeypatch.setenv("FEATURE_DATA_EOD_DISPLAY", "true")
    _seed(db, symbol="AAA", isin="INE222A01011", closes={date(2026, 10, 9): 10})
    _seed(db, symbol="BBB", isin="INE333A01011", closes={date(2026, 10, 9): 20})
    out = eod_prices.get_closes(["AAA", "INE333A01011", "NOPE"], on=date(2026, 10, 12))
    assert out["AAA"].close == Decimal("10") and out["INE333A01011"].close == Decimal("20")
    assert out["NOPE"] is None and set(out) == {"AAA", "INE333A01011", "NOPE"}


def _load_script():
    path = Path(__file__).resolve().parent.parent / "scripts" / "backfill_daily_prices.py"
    spec = importlib.util.spec_from_file_location("backfill_daily_prices", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cli_rejects_bad_ranges_and_missing_key(monkeypatch):
    mod = _load_script()
    assert mod.main(["--start", "2026-01-02", "--end", "2026-01-01"]) == 2
    assert mod.main(["--start", "2000-01-01", "--end", "2026-01-01"]) == 2
    _cfg(monkeypatch, key=None)
    assert mod.main(["--start", "2026-01-01", "--end", "2026-01-02"]) == 1


def test_client_eod_and_sync_methods():
    import httpx

    from services.research.client import MLEngineClient

    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        if request.url.path.endswith("/eod/2026-10-09"):
            return httpx.Response(200, json={"status": "ok", "rows": []})
        if request.url.path.endswith("/eod/2026-10-10"):
            return httpx.Response(404, json={"code": "NOT_INGESTED"})
        if request.url.path.endswith("/marketdata/sync"):
            return httpx.Response(409, json={"code": "ENGINE_BUSY"})
        return httpx.Response(503)

    client = MLEngineClient("http://engine", "secret", transport=httpx.MockTransport(handler))
    assert client.eod(date(2026, 10, 9)) == {"status": "ok", "rows": []}
    assert client.eod(date(2026, 10, 10)) is None
    assert client.marketdata_sync(date(2026, 10, 9)) == "busy"
    with pytest.raises(MLEngineUnavailable):
        client.eod(date(2026, 10, 11))
