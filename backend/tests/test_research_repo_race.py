"""insert_on_demand_report: the loser of a same-key race returns the winner's row, not a 500."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from models.db_models import Base, ResearchReportRow
from repositories import research_repo as repo


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _report(uid: int) -> dict:
    return {
        "report_id": f"00000000-0000-4000-8000-{uid:012d}",
        "engine_version": "re-1.0.0+fv1",
        "status": "ok",
        "symbol": "TCS",
        "as_of": {"market_date": "2026-10-09"},
        "coverage": {"in_universe": True},
        "model_card": {"procedure_id": "lgbm-rank-v1"},
    }


def _count(session):
    return session.query(ResearchReportRow).filter(ResearchReportRow.symbol == "TCS").count()


def test_loser_of_the_race_gets_the_existing_row(session, monkeypatch):
    winner = repo.insert_on_demand_report(session, _report(1), requested_by_user_id=1)
    real = repo._existing_report
    calls = []

    def first_call_misses(sess, row):
        calls.append(1)
        return None if len(calls) == 1 else real(sess, row)

    monkeypatch.setattr(repo, "_existing_report", first_call_misses)
    got = repo.insert_on_demand_report(session, _report(2), requested_by_user_id=2)
    assert got.id == winner.id
    assert _count(session) == 1


def test_integrity_error_without_a_winner_is_reraised(session, monkeypatch):
    repo.insert_on_demand_report(session, _report(1), requested_by_user_id=1)
    monkeypatch.setattr(repo, "_existing_report", lambda *_a: None)
    with pytest.raises(IntegrityError):
        repo.insert_on_demand_report(session, _report(2), requested_by_user_id=2)


def test_normal_path_inserts(session):
    row = repo.insert_on_demand_report(session, _report(3), requested_by_user_id=1)
    assert row.id is not None and _count(session) == 1
