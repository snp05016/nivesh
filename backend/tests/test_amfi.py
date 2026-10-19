"""services/amfi.py: NAVAll.txt parsing and the idempotent harvest. Hermetic (in-memory DB, no network)."""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from models.db_models import DailyPrice, Instrument, MutualFund
from services import amfi
from services.mutual_fund_service import SAMPLE_SCHEME_CODES
from tests.data_db import patch_get_session

TEXT = (Path(__file__).parent / "fixtures" / "amfi_navall_sample.txt").read_text()
TODAY = date(2026, 10, 9)


@pytest.fixture
def db(monkeypatch):
    factory = patch_get_session(monkeypatch)
    monkeypatch.setattr(amfi, "MIN_ROWS", 1)
    with factory() as s:
        yield s


def test_parse_context_plan_flags_and_isins():
    rows = {r.scheme_code: r for r in amfi.parse_navall(TEXT)}
    assert set(rows) == {"100001", "100002", "100004", "200001", "200002"}  # N.A. NAV skipped
    r = rows["100001"]
    assert (r.category, r.sub_category, r.scheme_type) == ("Equity", "Large Cap Fund", "open")
    assert r.amc_name == "Alpha Mutual Fund" and r.is_direct_plan and r.is_growth_plan
    assert (r.isin_growth, r.isin_reinvest, r.nav, r.nav_date) == ("INF000A01011", "INF000A01029", 123.4567, TODAY)
    idcw = rows["100002"]
    assert not idcw.is_direct_plan and not idcw.is_growth_plan and idcw.isin_reinvest is None
    assert rows["100004"].isin_reinvest is None and rows["100004"].nav == 1234.5
    close = rows["200002"]
    assert (close.scheme_type, close.category, close.sub_category) == ("close", "Other", "Income")
    assert rows["200001"].amc_name == "Beta Mutual Fund"


def test_heading_normalisation():
    text = ("Interval Fund Schemes(Other Scheme - Index Funds)\nAMC\n"
            "1;INF000C01011;-;X Direct Growth;10;09-Oct-2026\n"
            "Open Ended Schemes(Solution Oriented Scheme - Retirement Fund)\nAMC\n"
            "2;INF000C01029;-;Y Plan;10;09-Oct-2026\n")
    a, b = amfi.parse_navall(text)
    assert (a.scheme_type, a.category, a.sub_category) == ("interval", "Other", "Index Funds")
    assert (b.category, b.sub_category) == ("Solution Oriented", "Retirement Fund")


def test_rows_before_any_heading_are_other():
    row = amfi.parse_navall("AMC\n1;INF000C01011;-;Plain Fund;10;09-Oct-2026\n")[0]
    assert row.scheme_type is None and row.category == "Other"


def test_harvest_inserts_funds_instruments_and_fresh_open_growth_history(db):
    out = amfi.harvest(text=TEXT, today=TODAY)
    assert out == {"parsed": 5, "funds_inserted": 5, "funds_updated": 0, "history_rows": 2, "deactivated": 0}
    fund = db.query(MutualFund).filter_by(scheme_code="100001").one()
    assert fund.scheme_name == fund.fund_name and fund.nav_source == "amfi" and fund.nav_date == "2026-10-09"
    assert fund.is_active and fund.category == "Equity" and fund.aum_cr is None
    inst = db.query(Instrument).filter_by(amfi_scheme_code="100001").one()
    assert (inst.isin, inst.isin_alt, inst.asset_class) == ("INF000A01011", "INF000A01029", "MF")
    assert db.query(Instrument).filter_by(asset_class="MF").count() == 5
    prices = db.query(DailyPrice).all()
    assert {p.instrument_id for p in prices} == {
        db.query(Instrument).filter_by(amfi_scheme_code=c).one().id for c in ("100001", "200001")
    }
    assert all(p.source == "amfi" for p in prices)


def test_rerun_is_idempotent_and_restatement_updates(db):
    amfi.harvest(text=TEXT, today=TODAY)
    again = amfi.harvest(text=TEXT, today=TODAY)
    assert again["history_rows"] == 0 and again["funds_inserted"] == 0 and again["funds_updated"] == 5
    assert db.query(DailyPrice).count() == 2
    amfi.harvest(text=TEXT.replace("123.4567", "124.0000"), today=TODAY)
    db.expire_all()
    inst = db.query(Instrument).filter_by(amfi_scheme_code="100001").one()
    price = db.query(DailyPrice).filter_by(instrument_id=inst.id).one()
    assert price.close == Decimal("124.0000") and db.query(DailyPrice).count() == 2


def test_tracked_non_growth_scheme_gets_history(db):
    amfi.harvest(text=TEXT, today=TODAY)
    fund = db.query(MutualFund).filter_by(scheme_code="100002").one()
    fund.track_nav = True
    db.commit()
    out = amfi.harvest(text=TEXT, today=TODAY)
    assert out["history_rows"] == 1


def test_absent_scheme_is_deactivated_but_sample_codes_are_untouched(db):
    amfi.harvest(text=TEXT, today=TODAY)
    sample_code = next(iter(SAMPLE_SCHEME_CODES))
    db.add(MutualFund(scheme_code=sample_code, fund_name="Demo", amc="Demo", category="Equity",
                      nav_source="amfi", is_active=True))
    db.commit()
    trimmed = TEXT.replace("200001;INF000B01011;INF000B01029;Beta Flexi Cap Fund - Direct Plan - Growth;88.80;09-Oct-2026\n", "")
    out = amfi.harvest(text=trimmed, today=TODAY)
    assert out["deactivated"] == 1
    db.expire_all()
    assert db.query(MutualFund).filter_by(scheme_code="200001").one().is_active is False
    assert db.query(Instrument).filter_by(amfi_scheme_code="200001").one().status == "inactive"
    assert db.query(MutualFund).filter_by(scheme_code=sample_code).one().is_active is True


def test_flag_off_skips_and_short_file_raises(db, monkeypatch):
    with pytest.raises(RuntimeError, match="AMFI file too short"):
        monkeypatch.setattr(amfi, "MIN_ROWS", 5000)
        amfi.harvest(text=TEXT, today=TODAY)
    monkeypatch.setenv("FEATURE_DATA_MF_UNIVERSE", "false")
    assert amfi.harvest(text=TEXT, today=TODAY) == {"skipped": "flag_off"}
    assert db.query(MutualFund).count() == 0
