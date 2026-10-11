"""GH-689: /dashboard-data returns at most 50 summary rows without the heavy
raw_output/full_json fields; those come from /dashboard-data/analysis/{id}.

Uses the conftest sqlite test DB and stub user 990001.
"""
import json
from datetime import datetime, timedelta

import pytest

import main
from database import get_session
from models.db_models import AnalysisHistory  # pyright: ignore[reportMissingImports]

_TICKER_PREFIX = "GH689T"
# Far-future timestamps so these rows are the newest in the shared test DB.
_BASE = datetime(2099, 1, 1)


@pytest.fixture
def as_admin(monkeypatch):
    monkeypatch.setattr(main, "require_admin", lambda _authorization=None: 1)


@pytest.fixture
def sixty_rows():
    ids = []
    with get_session() as session:
        for i in range(60):
            row = AnalysisHistory(
                user_id=990001,
                ticker=f"{_TICKER_PREFIX}{i}",
                analysis_date="2099-01-01",
                signal="BUY",
                confidence_pct=70,
                raw_output=f"raw {i}",
                full_json=json.dumps({"i": i}),
                was_correct=(i % 2 == 0),
                created_at=_BASE + timedelta(minutes=i),
            )
            session.add(row)
            session.flush()
            ids.append(int(row.id))  # type: ignore[arg-type]
        session.commit()
    yield ids
    with get_session() as session:
        session.query(AnalysisHistory).filter(AnalysisHistory.id.in_(ids)).delete(synchronize_session=False)
        session.commit()


def test_dashboard_data_is_capped_and_light(client, as_admin, sixty_rows):
    resp = client.get("/dashboard-data")
    assert resp.status_code == 200, resp.text
    hist = resp.json()["historical_analyses"]

    assert len(hist) == 50
    assert [h["ticker"] for h in hist[:3]] == [f"{_TICKER_PREFIX}59", f"{_TICKER_PREFIX}58", f"{_TICKER_PREFIX}57"]
    for h in hist:
        assert "raw_output" not in h and "full_json" not in h
        assert "was_correct" in h
    assert hist[0]["was_correct"] is False  # i=59


def test_analysis_detail_endpoint(client, as_admin, sixty_rows):
    target = sixty_rows[5]
    resp = client.get(f"/dashboard-data/analysis/{target}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == target
    assert body["raw_output"] == "raw 5"
    assert json.loads(body["full_json"]) == {"i": 5}

    assert client.get("/dashboard-data/analysis/987654321").status_code == 404


def test_analysis_detail_requires_admin(client, sixty_rows):
    resp = client.get(f"/dashboard-data/analysis/{sixty_rows[0]}")
    assert resp.status_code in (401, 403)
