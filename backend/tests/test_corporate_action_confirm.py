"""I18: guarded auto-apply, per-(user, group) proposals, and the apply / dismiss / undo API. Hermetic."""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security import require_auth
from models.db_models import (
    CorporateAction, CorporateActionApplication, DailyPrice, Instrument, Portfolio, PortfolioGroup, Transaction, User,
)
from routers import corporate_actions as ca_router
from services import corporate_actions as ca_service
from services.ledger_service import apply_split_events, record_transaction
from tests.data_db import patch_get_session

EX = date(2026, 3, 2)
EVENTS = [(EX, 2.0)]
FLAG_ENV = "FEATURE_DATA_CORP_ACTIONS_CONFIRM"


@pytest.fixture
def db(monkeypatch):
    factory = patch_get_session(monkeypatch)
    monkeypatch.delenv(FLAG_ENV, raising=False)
    monkeypatch.delenv(FLAG_ENV + "_USERS", raising=False)
    with factory() as s:
        for uid in (1, 2):
            s.add(User(id=uid, username=f"u{uid}", password_hash="x", display_name=f"U{uid}"))
        s.commit()
        yield s


def _buy(ticker, qty, price, when, user_id=1, group_id=None):
    record_transaction(user_id=user_id, ticker=ticker, transaction_type="BUY", quantity=qty, price=price,
                       company_name="Test Co", date=when, group_id=group_id)


def _created(db, ticker, when, user_id=1):
    """Pretend the ledger rows of (user, ticker) were entered in the app at `when` (naive UTC; None = unknown)."""
    db.query(Transaction).filter_by(user_id=user_id, ticker=ticker).update({"created_at": when})
    db.commit()


def _held(db, ticker, user_id=1):
    db.expire_all()
    row = db.query(Portfolio).filter_by(user_id=user_id, ticker=ticker, group_name="holdings").first()
    return (float(row.shares), float(row.buy_price)) if row else None


def _splits(db, ticker, user_id=1):
    return db.query(Transaction).filter_by(user_id=user_id, ticker=ticker, transaction_type="SPLIT").all()


def _record(ticker):
    return ca_service.record_events(ticker, EVENTS)


def _jan10():
    return datetime(2026, 1, 10, tzinfo=timezone.utc)


# ── ratio text and records ──────────────────────────────────────────────────

@pytest.mark.parametrize("ratio,text", [
    (2.0, "1 share became 2"), (1.5, "2 shares became 3"), (5.0, "1 share became 5"),
    (10.0, "1 share became 10"), (1.3333, "1 share became 1.333"), (0.5, "2 shares became 1"),
])
def test_ratio_text(ratio, text):
    assert ca_service.ratio_text(ratio) == text


def _seed_prices(db, symbol, event, prev_close=1450.0):
    inst = Instrument(asset_class="EQ", symbol=symbol, name=symbol, source="t", status="active")
    db.add(inst)
    db.flush()
    stamp = datetime(2026, 3, 1)
    db.add(DailyPrice(instrument_id=inst.id, trade_date=date(2026, 2, 27), close=2900, source="nse_bhavcopy", ingested_at=stamp))
    db.add(DailyPrice(instrument_id=inst.id, trade_date=EX, close=1450, prev_close=prev_close, event=event,
                      source="nse_bhavcopy", ingested_at=stamp))
    db.commit()


def test_record_events_upserts_once_with_confirmation(db):
    _seed_prices(db, "SPLITCO", "split")
    first = _record("SPLITCO.NS")
    second = _record("SPLITCO")
    assert first == second and len(first) == 1
    row = db.query(CorporateAction).one()
    assert (row.ticker, row.action_type, row.ex_on, row.source) == ("SPLITCO", "SPLIT_OR_BONUS", EX, "yfinance")
    assert row.ex_date == "2026-03-02" and float(row.ratio) == 2.0 and row.nse_confirmed is True
    assert row.purpose == "Share split or bonus: 1 share became 2"


def test_nse_confirmed_false_for_unverified_and_none_without_rows(db):
    _seed_prices(db, "UNVER", "ca_unverified")
    _record("UNVER")
    _record("NOROWS")
    flags = {r.ticker: r.nse_confirmed for r in db.query(CorporateAction)}
    assert flags == {"UNVER": False, "NOROWS": None}


# ── the guard ───────────────────────────────────────────────────────────────

def test_flag_off_unambiguous_buy_auto_applies_without_application(db):
    _buy("AUTO", 100, 2000.0, _jan10())
    _created(db, "AUTO", datetime(2026, 1, 10))
    ids = _record("AUTO")
    assert apply_split_events(1, "AUTO", EVENTS, action_ids=ids) == 1
    assert _held(db, "AUTO")[0] == pytest.approx(200.0)
    assert db.query(CorporateActionApplication).count() == 0


def test_flag_off_back_dated_buy_is_only_recorded(db):
    _buy("BACK", 100, 2000.0, _jan10())
    _created(db, "BACK", datetime(2026, 3, 5))
    ids = _record("BACK")
    assert apply_split_events(1, "BACK", EVENTS, action_ids=ids) == 0
    assert _splits(db, "BACK") == [] and db.query(CorporateActionApplication).count() == 0
    assert _held(db, "BACK")[0] == pytest.approx(100.0)
    assert db.query(CorporateAction).count() == 1


def test_null_created_at_counts_as_ambiguous(db):
    _buy("NOCR", 100, 2000.0, _jan10())
    _created(db, "NOCR", None)
    assert apply_split_events(1, "NOCR", EVENTS, action_ids=_record("NOCR")) == 0
    assert _splits(db, "NOCR") == []


def test_created_on_ex_date_in_ist_is_ambiguous(db):
    _buy("EDGE", 100, 2000.0, _jan10())
    _created(db, "EDGE", datetime(2026, 3, 1, 19, 0))  # 00:30 IST on the ex-date
    assert apply_split_events(1, "EDGE", EVENTS, action_ids=_record("EDGE")) == 0


def test_flag_on_back_dated_buy_gets_one_pending_application(db, monkeypatch):
    monkeypatch.setenv(FLAG_ENV, "true")
    _buy("PEND", 100, 2000.0, _jan10())
    _created(db, "PEND", datetime(2026, 3, 5))
    _buy("GOOD", 100, 2000.0, _jan10())
    _created(db, "GOOD", datetime(2026, 1, 10))
    ids_p, ids_g = _record("PEND"), _record("GOOD")
    assert apply_split_events(1, "PEND", EVENTS, action_ids=ids_p) == 0
    assert apply_split_events(1, "PEND", EVENTS, action_ids=ids_p) == 0  # idempotent
    apps = db.query(CorporateActionApplication).all()
    assert len(apps) == 1 and apps[0].status == "pending" and float(apps[0].shares_before) == 100
    assert _splits(db, "PEND") == [] and _held(db, "PEND")[0] == pytest.approx(100.0)
    assert apply_split_events(1, "GOOD", EVENTS, action_ids=ids_g) == 1
    assert _held(db, "GOOD")[0] == pytest.approx(200.0)


def test_allowlisted_user_gets_a_proposal_while_flag_off(db, monkeypatch):
    monkeypatch.setenv(FLAG_ENV + "_USERS", "1")
    for uid in (1, 2):
        _buy("COHORT", 100, 2000.0, _jan10(), user_id=uid)
        _created(db, "COHORT", datetime(2026, 3, 5), user_id=uid)
    ids = _record("COHORT")
    apply_split_events(1, "COHORT", EVENTS, action_ids=ids)
    apply_split_events(2, "COHORT", EVENTS, action_ids=ids)
    assert [a.user_id for a in db.query(CorporateActionApplication)] == [1]


def _two_group_position(db, ticker, created):
    g1 = PortfolioGroup(user_id=1, name="Core", is_default=True)
    g2 = PortfolioGroup(user_id=1, name="Satellite", is_default=False)
    db.add_all([g1, g2])
    db.commit()
    _buy(ticker, 100, 2000.0, _jan10(), group_id=g1.id)
    _buy(ticker, 40, 2000.0, _jan10(), group_id=g2.id)
    _created(db, ticker, created)
    return g1.id, g2.id


def test_two_groups_give_two_proposals_and_apply_hits_only_its_group(db, monkeypatch):
    monkeypatch.setenv(FLAG_ENV, "true")
    g1, g2 = _two_group_position(db, "TWOG", datetime(2026, 3, 5))
    ids = _record("TWOG")
    apply_split_events(1, "TWOG", EVENTS, action_ids=ids)
    apps = db.query(CorporateActionApplication).order_by(CorporateActionApplication.group_id).all()
    assert [(a.group_id, float(a.shares_before)) for a in apps] == [(g1, 100.0), (g2, 40.0)]
    assert _splits(db, "TWOG") == []
    from services.ledger_service import apply_corporate_action
    apply_corporate_action(1, apps[1].id)
    db.expire_all()
    assert [t.group_id for t in _splits(db, "TWOG")] == [g2]


# ── API ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def api(db, monkeypatch):
    monkeypatch.setenv(FLAG_ENV, "true")
    current = {"uid": 1}
    app = FastAPI()
    app.include_router(ca_router.router)
    app.dependency_overrides[require_auth] = lambda: current["uid"]
    client = TestClient(app)
    client.current = current
    return client


def _pending(db, ticker="API"):
    _buy(ticker, 100, 2000.0, _jan10())
    _created(db, ticker, datetime(2026, 3, 5))
    apply_split_events(1, ticker, EVENTS, action_ids=_record(ticker))
    return db.query(CorporateActionApplication).one().id


def test_list_apply_and_double_apply(api, db):
    app_id = _pending(db)
    items = api.get("/api/v1/portfolio/corporate-actions").json()["items"]
    assert len(items) == 1
    item = items[0]
    assert item["status"] == "pending" and item["ticker"] == "API" and item["ratio_text"] == "1 share became 2"
    assert item["shares_before"] == 100 and item["shares_after"] == 200 and item["ex_date"] == "2026-03-02"
    assert item["group_name"] == "Core Holdings" and item["undo_until"] is None
    assert item["source"] == "Yahoo Finance corporate actions" and item["action_label"] == "Share split or bonus"
    resp = api.post(f"/api/v1/portfolio/corporate-actions/{app_id}/apply")
    assert resp.status_code == 200
    body = resp.json()
    assert body["holding"] == {"ticker": "API", "shares": 200.0, "avg_price": 1000.0}
    assert body["item"]["status"] == "applied" and body["item"]["undo_until"] is not None
    again = api.post(f"/api/v1/portfolio/corporate-actions/{app_id}/apply")
    assert again.status_code == 409 and again.json() == {"detail": {"code": "INVALID_STATE", "status": "applied"}}


def test_dismiss_then_undo_returns_to_pending(api, db):
    app_id = _pending(db)
    resp = api.post(f"/api/v1/portfolio/corporate-actions/{app_id}/dismiss")
    assert resp.status_code == 200 and resp.json()["item"]["status"] == "dismissed" and resp.json()["holding"] is None
    assert _held(db, "API")[0] == pytest.approx(100.0)
    undo = api.post(f"/api/v1/portfolio/corporate-actions/{app_id}/undo")
    assert undo.status_code == 200 and undo.json()["item"]["status"] == "pending"
    row = db.query(CorporateActionApplication).one()
    db.refresh(row)
    assert row.decided_at is None and row.transaction_id is None


def test_apply_then_undo_deletes_only_the_linked_split_and_job_does_not_reapply(api, db):
    app_id = _pending(db)
    api.post(f"/api/v1/portfolio/corporate-actions/{app_id}/apply")
    unrelated = Transaction(user_id=1, ticker="API", transaction_type="SPLIT", quantity=1.0, price=0.0,
                            date=datetime(2020, 1, 1, tzinfo=timezone.utc), notes="manual")
    db.add(unrelated)
    db.commit()
    unrelated_id = unrelated.id
    undo = api.post(f"/api/v1/portfolio/corporate-actions/{app_id}/undo")
    assert undo.status_code == 200 and undo.json()["item"]["status"] == "pending"
    assert undo.json()["holding"]["shares"] == pytest.approx(100.0)
    assert [t.id for t in _splits(db, "API")] == [unrelated_id]  # only the linked SPLIT was deleted
    ids = {EX: db.query(CorporateAction).one().id}
    assert apply_split_events(1, "API", EVENTS, action_ids=ids) == 0
    assert db.query(CorporateActionApplication).count() == 1 and len(_splits(db, "API")) == 1


def test_undo_after_31_days_conflicts(api, db):
    app_id = _pending(db)
    api.post(f"/api/v1/portfolio/corporate-actions/{app_id}/dismiss")
    row = db.query(CorporateActionApplication).one()
    row.decided_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=31)
    db.commit()
    resp = api.post(f"/api/v1/portfolio/corporate-actions/{app_id}/undo")
    assert resp.status_code == 409 and resp.json()["detail"]["code"] == "INVALID_STATE"
    assert resp.json()["detail"]["status"] == "dismissed"
    assert api.get("/api/v1/portfolio/corporate-actions").json()["items"] == []  # outside the 30-day window


def test_foreign_id_is_404_and_flag_off_is_feature_disabled(api, db, monkeypatch):
    app_id = _pending(db)
    api.current["uid"] = 2
    for path in (f"{app_id}/apply", f"{app_id}/dismiss", f"{app_id}/undo"):
        resp = api.post(f"/api/v1/portfolio/corporate-actions/{path}")
        assert resp.status_code == 404 and resp.json() == {"detail": {"code": "NOT_FOUND"}}
    assert api.post("/api/v1/portfolio/corporate-actions/9999/apply").json() == {"detail": {"code": "NOT_FOUND"}}
    monkeypatch.setenv(FLAG_ENV, "false")
    resp = api.get("/api/v1/portfolio/corporate-actions")
    assert resp.status_code == 404
    assert resp.json() == {"detail": {"code": "FEATURE_DISABLED", "feature": "data_corp_actions_confirm"}}
    monkeypatch.setenv(FLAG_ENV + "_USERS", "2")
    assert api.get("/api/v1/portfolio/corporate-actions").status_code == 200
