"""DB-32: latest_signals_by_ticker reads the newest analyses per ticker in one
SELECT and never loads full_json / raw_output."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from models.db_models import AnalysisHistory, Base  # pyright: ignore[reportMissingImports]
from repositories.analysis_repo import latest_signals_by_ticker

_SIGNALS = ["BEARISH", "HOLD", "BULLISH", "HOLD", "BULLISH"]  # oldest -> newest


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    t0 = datetime(2026, 10, 1, 9, 0, 0)
    for ticker in ("TCS", "INFY", "RELIANCE"):
        for i, signal in enumerate(_SIGNALS):
            s.add(AnalysisHistory(
                user_id=1 if i % 2 == 0 else 2,
                ticker=ticker,
                analysis_date=(t0 + timedelta(days=i)).date().isoformat(),
                signal=signal,
                confidence_pct=50 + i,
                created_at=t0 + timedelta(days=i),
                full_json="x" * 20_000,
                raw_output="y" * 20_000,
            ))
    s.commit()

    statements: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _count(_conn, _cursor, statement, *_args):
        statements.append(statement)

    yield s, statements
    s.close()
    engine.dispose()


def test_newest_per_ticker_in_one_select_without_payload_columns(db):
    s, statements = db
    out = latest_signals_by_ticker(s, ["TCS", "INFY"])

    assert set(out) == {"TCS", "INFY"}
    for rows in out.values():
        assert len(rows) == 1
        assert rows[0]["signal"] == "BULLISH"
        assert rows[0]["confidence_pct"] == 54
        assert rows[0]["created_at"] == datetime(2026, 10, 5, 9, 0, 0)
        assert rows[0]["analysis_date"] == "2026-10-05"
    assert len(statements) == 1
    assert "full_json" not in statements[0]
    assert "raw_output" not in statements[0]


def test_two_newest_in_descending_order(db):
    s, _ = db
    rows = latest_signals_by_ticker(s, ["RELIANCE"], per_ticker=2)["RELIANCE"]
    assert [r["signal"] for r in rows] == ["BULLISH", "HOLD"]
    assert rows[0]["created_at"] > rows[1]["created_at"]


def test_user_filter(db):
    s, _ = db
    # user 2 owns the 2nd and 4th analyses (HOLD, HOLD); the newest of them is day 4.
    rows = latest_signals_by_ticker(s, ["TCS"], user_id=2)["TCS"]
    assert rows[0]["confidence_pct"] == 53
    assert rows[0]["signal"] == "HOLD"


def test_empty_ticker_list_issues_no_query(db):
    s, statements = db
    assert latest_signals_by_ticker(s, []) == {}
    assert statements == []
