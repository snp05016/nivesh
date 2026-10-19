"""Habit cluster schema (revision c4e81f2a9b07): notification prefs, delivery log,
stock_events and portfolio.added_price.

Hermetic: in-memory or tmp_path SQLite built with Base.metadata.create_all; the
revision runs through alembic Operations on that connection. No app import
beyond the ORM models, no network.
"""

from __future__ import annotations

import importlib.util
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models.db_models import (  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)
    Base,
    InAppNotification,
    Portfolio,
    StockEvent,
    User,
    UserPreference,
)

REVISION_FILE = (
    Path(__file__).resolve().parents[1]
    / "migrations" / "versions" / "c4e81f2a9b07_habit_notifications_events_watchlist.py"
)

HABIT_CHECKS = {
    "user_preferences": {
        "ck_user_preferences_quiet_start",
        "ck_user_preferences_quiet_end",
        "ck_user_preferences_brief_time",
        "ck_user_preferences_event_scope",
    },
    "in_app_notifications": {"ck_in_app_notifications_status"},
    "portfolio": {"ck_portfolio_added_price_positive"},
}
HABIT_COLUMNS = {
    "user_preferences": {
        "push_categories", "quiet_enabled", "quiet_start_min", "quiet_end_min",
        "quiet_days", "time_zone", "brief_time_min", "event_scope",
    },
    "in_app_notifications": {
        "category", "channel", "status", "dedupe_key", "error", "attempts", "sent_at", "opened_at",
    },
    "portfolio": {"added_price"},
}
NOTIF_INDEXES = {"uq_in_app_notifications_dedupe_key", "ix_in_app_notifications_user_created"}
EVENT_INDEXES = {"ix_stock_events_symbol_published", "ix_stock_events_event_date"}


@pytest.fixture()
def session():
    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def _user(session, name: str) -> int:
    u = User(username=name, password_hash="x", display_name=name)
    session.add(u)
    session.flush()
    return cast(int, u.id)


def _notif(user_id: int, dedupe_key: str | None, **extra) -> InAppNotification:
    return InAppNotification(user_id=user_id, type="system", title="t", body="b", dedupe_key=dedupe_key, **extra)


def _event(dedupe_key: str, event_type: str = "board_meeting") -> StockEvent:
    return StockEvent(
        symbol="TCS",
        event_type=event_type,
        severity="medium",
        title="Board meeting for financial results",
        source_feed="Board_Meetings",
        source_url="https://nsearchives.nseindia.com/corporate/x.pdf",
        published_at=datetime(2026, 10, 9, 6, 50, 39),
        dedupe_key=dedupe_key,
    )


# ---------------------------------------------------------------------------
# ORM (create_all)
# ---------------------------------------------------------------------------

def test_user_preference_defaults(session):
    uid = _user(session, "prefs_defaults")
    session.add(UserPreference(user_id=uid))
    session.commit()

    pref = session.query(UserPreference).filter_by(user_id=uid).one()
    assert pref.quiet_enabled is True
    assert (pref.quiet_start_min, pref.quiet_end_min) == (1320, 420)
    assert pref.time_zone == "Asia/Kolkata"
    assert pref.brief_time_min == 510
    assert pref.event_scope == "holdings"
    assert pref.push_categories is None and pref.quiet_days is None


def test_user_preference_server_defaults_fill_raw_inserts(session):
    uid = _user(session, "prefs_raw")
    session.execute(sa.text("INSERT INTO user_preferences (user_id) VALUES (:u)"), {"u": uid})
    row = session.execute(sa.text(
        "SELECT quiet_enabled, quiet_start_min, quiet_end_min, time_zone, brief_time_min, event_scope "
        "FROM user_preferences WHERE user_id = :u"
    ), {"u": uid}).one()
    assert tuple(row) == (1, 1320, 420, "Asia/Kolkata", 510, "holdings")


@pytest.mark.parametrize("field,value", [
    ("quiet_start_min", 1440),
    ("quiet_end_min", -1),
    ("brief_time_min", 359),
    ("brief_time_min", 646),
    ("event_scope", "everything"),
])
def test_user_preference_checks(session, field, value):
    uid = _user(session, f"prefs_ck_{field}_{value}")
    session.add(UserPreference(user_id=uid, **{field: value}))
    with pytest.raises(IntegrityError):
        session.commit()


def test_notification_dedupe_key_unique_but_nulls_repeat(session):
    uid = _user(session, "notif_dedupe")
    session.add_all([_notif(uid, None), _notif(uid, None)])
    session.commit()

    row = session.query(InAppNotification).filter_by(user_id=uid).first()
    assert row is not None
    assert (row.channel, row.status, row.attempts) == ("inbox", "delivered", 0)

    session.add_all([_notif(uid, "event:1:1"), _notif(uid, "event:1:1")])
    with pytest.raises(IntegrityError):
        session.commit()


def test_notification_status_check(session):
    uid = _user(session, "notif_status")
    session.add(_notif(uid, None, status="bogus"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_stock_event_dedupe_key_unique(session):
    session.add(_event("a" * 64))
    session.commit()
    stored = session.query(StockEvent).one()
    assert stored.source == "nse_rss" and stored.created_at is not None

    session.add(_event("a" * 64))
    with pytest.raises(IntegrityError):
        session.commit()


def test_stock_event_type_check(session):
    session.add(_event("b" * 64, event_type="x"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_portfolio_added_price_check(session):
    uid = _user(session, "watch_added")
    session.add(Portfolio(
        user_id=uid, ticker="TCS.NS", company_name="TCS", shares=0, buy_price=0,
        group_name="watchlist", added_price=Decimal("3850.5"),
    ))
    session.add(Portfolio(user_id=uid, ticker="INFY.NS", company_name="Infosys", shares=0, buy_price=0,
                          group_name="watchlist"))
    session.commit()

    session.add(Portfolio(
        user_id=uid, ticker="WIPRO.NS", company_name="Wipro", shares=0, buy_price=0,
        group_name="watchlist", added_price=0,
    ))
    with pytest.raises(IntegrityError):
        session.commit()


# ---------------------------------------------------------------------------
# Migration round trip on a create_all database
# ---------------------------------------------------------------------------

def _load_revision():
    spec = importlib.util.spec_from_file_location(REVISION_FILE.stem, REVISION_FILE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, fn) -> None:
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            fn()


def _schema(engine) -> dict:
    insp = sa.inspect(engine)
    out: dict = {"tables": set(insp.get_table_names())}
    for table in HABIT_COLUMNS:
        out[table] = {
            "columns": {c["name"] for c in insp.get_columns(table)},
            "indexes": {ix["name"] for ix in insp.get_indexes(table)},
            "checks": {c["name"] for c in insp.get_check_constraints(table)},
        }
    if "stock_events" in out["tables"]:
        out["stock_events"] = {
            "indexes": {ix["name"] for ix in insp.get_indexes("stock_events")},
            "uniques": {u["name"] for u in insp.get_unique_constraints("stock_events")},
            "checks": {c["name"] for c in insp.get_check_constraints("stock_events")},
        }
    return out


def _assert_upgraded(engine) -> None:
    s = _schema(engine)
    assert "stock_events" in s["tables"]
    for table, columns in HABIT_COLUMNS.items():
        assert columns <= s[table]["columns"], table
        assert HABIT_CHECKS[table] <= s[table]["checks"], table
    assert NOTIF_INDEXES <= s["in_app_notifications"]["indexes"]
    events = s["stock_events"]
    assert EVENT_INDEXES <= events["indexes"]
    assert "uq_stock_events_dedupe_key" in events["uniques"]
    assert {"ck_stock_events_type", "ck_stock_events_severity"} <= events["checks"]


def test_migration_roundtrip_on_create_all_database(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'habit_schema.db'}")
    try:
        Base.metadata.create_all(engine)
        revision = _load_revision()
        assert revision.revision == "c4e81f2a9b07"
        _assert_upgraded(engine)

        _run(engine, revision.upgrade)  # everything exists: a no-op
        _assert_upgraded(engine)

        with engine.begin() as conn:
            conn.execute(sa.text(
                "INSERT INTO users (id, username, password_hash, display_name) VALUES (1, 'h1', 'x', 'H')"
            ))
            conn.execute(sa.text(
                "INSERT INTO in_app_notifications (user_id, type, title, body, dedupe_key) "
                "VALUES (1, 'system', 't', 'b', 'k1')"
            ))

        _run(engine, revision.downgrade)
        s = _schema(engine)
        assert "stock_events" not in s["tables"]
        assert "dedupe_key" not in s["in_app_notifications"]["columns"]
        for table, columns in HABIT_COLUMNS.items():
            assert not columns & s[table]["columns"], table
            assert not HABIT_CHECKS[table] & s[table]["checks"], table
        assert not NOTIF_INDEXES & s["in_app_notifications"]["indexes"]
        # Earlier revisions' objects survive the table rebuilds.
        assert {"ck_portfolio_shares_positive", "ck_portfolio_asset_class"} <= s["portfolio"]["checks"]
        assert "ix_portfolio_user_ticker" in s["portfolio"]["indexes"]
        with engine.connect() as conn:
            assert conn.execute(sa.text("SELECT COUNT(*) FROM in_app_notifications")).scalar() == 1

        _run(engine, revision.upgrade)
        _assert_upgraded(engine)
        with engine.connect() as conn:
            row = conn.execute(sa.text(
                "SELECT channel, status, attempts, dedupe_key FROM in_app_notifications"
            )).one()
        assert tuple(row) == ("inbox", "delivered", 0, None)
    finally:
        engine.dispose()
