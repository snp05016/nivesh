"""services/instruments.py: EQUITY_L parsing, monotonic identity upserts, resolution and search. Hermetic."""
from datetime import date
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import database
from core.security import require_auth
from models.db_models import Base, Instrument, InstrumentAlias
from routers import search as search_router
from services import data_flags, instruments

FIXTURE = Path(__file__).parent / "fixtures" / "equity_l_sample.csv"
D1, D2, D3 = date(2026, 10, 1), date(2026, 10, 9), date(2026, 10, 12)


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)

    from contextlib import contextmanager

    @contextmanager
    def fake_get_session():
        s = factory()
        try:
            yield s
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    monkeypatch.setattr(database, "get_session", fake_get_session)
    with factory() as s:
        yield s


def _up(s, symbol, isin, seen_on, **kw):
    kw.setdefault("source", "nse_equity_l")
    return instruments.upsert_eq_identity(s, symbol=symbol, isin=isin, seen_on=seen_on, **kw)


def _aliases(s, kind=None):
    q = s.query(InstrumentAlias)
    return q.filter_by(kind=kind).all() if kind else q.all()


def test_parse_keeps_valid_eq_be_bz_rows():
    rows = instruments.parse_equity_list(FIXTURE.read_text())
    assert [r["symbol"] for r in rows] == ["RELIANCE", "NEWCO", "ZOMATO", "BZCO", "BECO", "NODATE"]
    new = next(r for r in rows if r["symbol"] == "NEWCO")
    assert new["listing_date"] == date(2026, 10, 7) and new["series"] == "EQ"
    assert next(r for r in rows if r["symbol"] == "NODATE")["listing_date"] is None


def test_insert_then_rename_keeps_id_and_writes_one_alias(db):
    a = _up(db, "ZOMATO", "INE758T01015", D1, name="Zomato Limited")
    db.commit()
    b = _up(db, "ETERNAL", "INE758T01015", D2, name="Eternal Limited")
    db.commit()
    assert a.id == b.id and b.symbol == "ETERNAL"
    aliases = _aliases(db, "symbol")
    assert [(x.value, x.valid_to) for x in aliases] == [("ZOMATO", D2)]


def test_isin_change_keeps_id_and_writes_one_isin_alias(db):
    a = _up(db, "ABC", "INE000A01011", D1)
    b = _up(db, "ABC", "INE000A01029", D2)
    assert a.id == b.id and b.isin == "INE000A01029"
    assert [x.value for x in _aliases(db, "isin")] == ["INE000A01011"]


def test_older_data_changes_nothing(db):
    _up(db, "ETERNAL", "INE758T01015", D2, name="Eternal Limited")
    inst = _up(db, "ZOMATO", "INE758T01015", D1, name="Zomato Limited")
    assert inst.symbol == "ETERNAL" and inst.name == "Eternal Limited" and inst.last_seen_on == D2
    assert _aliases(db) == []


def test_same_rename_twice_leaves_one_alias(db):
    _up(db, "ZOMATO", "INE758T01015", D1)
    _up(db, "ETERNAL", "INE758T01015", D2)
    _up(db, "ETERNAL", "INE758T01015", D2)
    _up(db, "ETERNAL", "INE758T01015", D3)
    assert len(_aliases(db)) == 1


def test_reused_symbol_frees_inactive_holder_but_not_newer_holder(db):
    old = _up(db, "OLDCO", "INE100A01010", D1)
    old.status = "inactive"
    db.commit()
    new = _up(db, "OLDCO", "INE200A01010", D2)
    assert new.id != old.id and new.symbol == "OLDCO"
    db.refresh(old)
    assert old.symbol is None and old.status == "inactive"
    assert [(a.value, a.instrument_id) for a in _aliases(db, "symbol")] == [("OLDCO", old.id)]

    # An older sighting of the same symbol matches the newer holder and changes nothing.
    stale = _up(db, "OLDCO", "INE300A01010", D1)
    assert stale.id == new.id and stale.isin == "INE200A01010" and stale.last_seen_on == D2


def test_symbol_held_by_newer_row_is_not_reassigned(db):
    holder = _up(db, "TAKEN", "INE400A01010", D2)
    mover = _up(db, "MOVER", "INE500A01010", D1)
    renamed = _up(db, "TAKEN", "INE500A01010", D1)  # older data wants mover's id to take TAKEN
    assert renamed.id == mover.id and renamed.symbol == "MOVER"
    db.refresh(holder)
    assert holder.symbol == "TAKEN" and holder.status == "active"


def _csv(n):
    lines = ["SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, ISIN NUMBER"]
    for i in range(n):
        lines.append(f"SYM{i:04d},Company {i},EQ,01-JAN-2020,INE{i:07d}01")
    return "\n".join(lines)


def test_small_file_raises_and_changes_nothing(db, monkeypatch):
    monkeypatch.setattr(instruments, "fetch_equity_list", lambda *a, **k: _csv(10))
    with pytest.raises(RuntimeError):
        instruments.refresh_equity_master(today=D2)
    assert db.query(Instrument).count() == 0


def test_refresh_inserts_and_deactivates_only_stale_rows(db, monkeypatch):
    _up(db, "GONE", "INE900A01019", date(2026, 9, 1))      # absent and stale
    _up(db, "RECENT", "INE901A01019", date(2026, 10, 5))   # absent but seen within 10 days
    db.commit()
    monkeypatch.setattr(instruments, "fetch_equity_list", lambda *a, **k: _csv(1600))
    out = instruments.refresh_equity_master(today=D2)
    assert out["inserted"] == 1600 and out["deactivated"] == 1
    db.expire_all()
    status = {i.symbol: i.status for i in db.query(Instrument).filter(Instrument.symbol.in_(["GONE", "RECENT"]))}
    assert status == {"GONE": "inactive", "RECENT": "active"}


def test_refresh_skipped_when_flag_off(db, monkeypatch):
    monkeypatch.setenv("FEATURE_DATA_INSTRUMENTS", "false")
    assert instruments.refresh_equity_master(today=D2) == {"skipped": "flag_off"}


def test_resolve_by_symbol_alias_and_old_isin(db):
    _up(db, "ZOMATO", "INE758T01015", D1)
    _up(db, "ETERNAL", "INE758T01015", D2)
    _up(db, "ETERNAL", "INE758T01016", D3)
    db.commit()
    assert instruments.resolve("zomato.ns").symbol == "ETERNAL"
    assert instruments.resolve(isin="INE758T01015").symbol == "ETERNAL"
    assert instruments.resolve("eternal").isin == "INE758T01016"
    assert instruments.resolve("NOPE") is None
    info = instruments.resolve_isin("INE758T01015")
    assert info["asset_class"] == "EQ" and info["symbol"] == "ETERNAL" and info["amfi_scheme_code"] is None


def test_upsert_mf_and_resolve_isin(db):
    inst = instruments.upsert_mf(db, scheme_code=119551, name="Fund A", isin="INF000A01011",
                                 isin_alt="INF000A01029", seen_on=D1)
    instruments.upsert_mf(db, scheme_code="119551", name="Fund A", isin="INF000A01011",
                          isin_alt="INF000A01037", seen_on=D2)
    db.commit()
    assert db.query(Instrument).filter_by(asset_class="MF").count() == 1
    assert [a.value for a in _aliases(db, "isin")] == ["INF000A01029"]
    info = instruments.resolve_isin("INF000A01037")
    assert info["amfi_scheme_code"] == "119551" and info["instrument_id"] == inst.id


def test_get_or_create_index_is_idempotent(db):
    a = instruments.get_or_create_index(db)
    b = instruments.get_or_create_index(db)
    assert a.id == b.id and a.asset_class == "INDEX" and a.source == "seed"


def _seed_listings(db):
    _up(db, "NEWCO", "INE999Z01011", D2, name="Newco Technologies Limited", series="EQ")
    _up(db, "RELIANCE", "INE002A01018", D2, name="Reliance Industries Limited", series="EQ")
    _up(db, "BZCO", "INE222B01012", D2, name="Trade To Trade Limited", series="BZ")
    _up(db, "PCT_CO", "INE555E01015", D2, name="Percent Limited", series="EQ")
    db.commit()


def test_search_excludes_bz_and_known_tickers_and_escapes_wildcards(db):
    _seed_listings(db)
    assert [r["ticker"] for r in instruments.search_new_listings("new", 10)] == ["NEWCO"]
    assert instruments.search_new_listings("BZCO", 10) == []
    assert instruments.search_new_listings("RELIANCE", 10) == []
    assert instruments.search_new_listings("%", 10) == []
    assert [r["ticker"] for r in instruments.search_new_listings("PCT_", 10)] == ["PCT_CO"]
    hit = instruments.search_new_listings("Newco Tech", 10)[0]
    assert hit == {"ticker": "NEWCO", "company_name": "Newco Technologies Limited", "sector": "", "exchange": "NSE"}


def _client():
    app = FastAPI()
    app.include_router(search_router.router)
    app.dependency_overrides[require_auth] = lambda: 1
    return TestClient(app)


def test_search_endpoint_appends_new_listing_only_when_flag_on(db, monkeypatch):
    _seed_listings(db)
    monkeypatch.setattr(search_router, "search_endpoint", lambda q, limit: [])
    on = _client().get("/api/v1/search", params={"query": "NEWCO"}).json()
    assert [r["ticker"] for r in on] == ["NEWCO"]
    monkeypatch.setenv("FEATURE_DATA_INSTRUMENTS", "false")
    assert _client().get("/api/v1/search", params={"query": "NEWCO"}).json() == []


def test_search_never_500s_on_db_error(db, monkeypatch):
    monkeypatch.setattr(search_router, "search_endpoint", lambda q, limit: [{"ticker": "X"}])

    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(instruments, "search_new_listings", boom)
    resp = _client().get("/api/v1/search", params={"query": "X"})
    assert resp.status_code == 200 and resp.json() == [{"ticker": "X"}]
