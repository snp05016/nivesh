"""Money: the ORM guard that hides mutual-fund Portfolio rows from non-money readers."""
from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

import database
from models.db_models import Portfolio, User

BACKEND = Path(__file__).resolve().parent.parent
ALLOWED_OPT_IN = {
    "database.py",
    "services/ledger_service.py",
    "scripts/reconcile_ledger.py",
    "routers/portfolio.py",
    "services/portfolio_snapshot.py",
}


@pytest.fixture()
def seeded():
    with database.get_session() as session:
        user = User(username=f"mfiso_{uuid4().hex[:12]}", password_hash="x", display_name="MF Isolation")
        session.add(user)
        session.commit()
        uid = int(user.id)
        eq = Portfolio(user_id=uid, ticker="INFY", company_name="Infosys", shares=1, buy_price=1,
                       group_name="holdings", asset_class="EQ")
        mf = Portfolio(user_id=uid, ticker="INF179K01VC4", company_name="Fund", shares=2, buy_price=3,
                       group_name="holdings", asset_class="MF")
        session.add_all([eq, mf])
        session.commit()
        ids = (uid, int(eq.id), int(mf.id))
    yield ids
    with database.get_session() as session:
        session.query(Portfolio).filter(Portfolio.user_id == ids[0]).delete()
        session.query(User).filter(User.id == ids[0]).delete()
        session.commit()


def test_orm_reads_hide_mf(seeded):
    uid, eq_id, mf_id = seeded
    with database.get_session() as session:
        rows = session.query(Portfolio).filter(Portfolio.user_id == uid).all()
        assert [r.ticker for r in rows] == ["INFY"]
        assert [t for (t,) in session.query(Portfolio.ticker).filter(Portfolio.user_id == uid).distinct()] == ["INFY"]
        pairs = session.query(Portfolio.user_id, Portfolio.ticker).filter(Portfolio.user_id == uid).all()
        assert [p[1] for p in pairs] == ["INFY"]
        sel = session.execute(select(Portfolio).where(Portfolio.user_id == uid)).scalars().all()
        assert [r.ticker for r in sel] == ["INFY"]
        assert session.get(Portfolio, mf_id) is None
        assert session.get(Portfolio, eq_id) is not None


def test_opt_in_returns_both_and_survives_refresh(seeded):
    uid, _eq_id, mf_id = seeded
    with database.get_session() as session:
        rows = session.query(Portfolio).execution_options(include_mf=True).filter(Portfolio.user_id == uid).all()
        assert {r.ticker for r in rows} == {"INFY", "INF179K01VC4"}
        mf = next(r for r in rows if r.asset_class == "MF")
        mf.shares = 5
        session.commit()
        assert mf.shares == 5  # expired-attribute refresh after commit still loads
        assert int(mf.id) == mf_id


def test_core_select_and_bulk_delete_see_everything(seeded):
    uid, *_ = seeded
    with database.get_session() as session:
        rows = session.execute(Portfolio.__table__.select().where(Portfolio.__table__.c.user_id == uid)).all()
        assert len(rows) == 2
        deleted = session.query(Portfolio).filter(Portfolio.user_id == uid).delete()
        assert deleted == 2
        session.rollback()


def test_extra_symbols_has_no_isin(seeded):
    from repositories import research_repo

    with database.get_session() as session:
        symbols = research_repo.extra_symbols(session)
    assert not any(s.startswith("INF179") for s in symbols)


def _py_files():
    for path in BACKEND.rglob("*.py"):
        rel = path.relative_to(BACKEND).as_posix()
        if rel.startswith(("tests/", "venv/", ".venv/", "migrations/")) or "/tests/" in rel:
            continue
        yield rel, path


def test_include_mf_allowlist():
    offenders = []
    for rel, path in _py_files():
        if "include_mf" not in path.read_text(encoding="utf-8", errors="ignore"):
            continue
        if rel in ALLOWED_OPT_IN:
            continue
        if re.fullmatch(r"services/money_[a-z0-9_]+\.py", rel):
            continue
        offenders.append(rel)
    assert not offenders, f"include_mf used outside the allowlist: {offenders}"


def test_money_services_import_no_llm_client():
    pattern = re.compile(r"^\s*(from|import)\s+.*(deepseek|anthropic|openai|_deepseek_chat|llm)", re.I | re.M)
    for path in (BACKEND / "services").glob("money_*.py"):
        assert not pattern.search(path.read_text(encoding="utf-8")), path.name
