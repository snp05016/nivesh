"""PERF-15: hot queries use an index, the migration matches the models, and the
nightly retention job prunes only old rows.

Runs on the conftest SQLite test DB (schema from metadata at app startup).
"""
import importlib.util
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

import database
from database import get_session
from models.db_models import AnalysisJob, Base, NewsArticle, PriceTarget  # pyright: ignore[reportMissingImports]

_HOT_QUERIES = {
    "analysis_jobs": "SELECT job_id FROM analysis_jobs WHERE status IN ('RUNNING', 'QUEUED')",
    "price_targets": "SELECT id, ticker FROM price_targets WHERE triggered = 0",
    "news_articles": "SELECT id, headline FROM news_articles ORDER BY published_at DESC LIMIT 15",
    "youtube_videos": "SELECT id FROM youtube_videos ORDER BY published_at DESC LIMIT 15",
    "analysis_history": (
        "SELECT id FROM analysis_history WHERE ticker = 'TCS' AND scan_type = 'standard' "
        "ORDER BY created_at DESC LIMIT 1"
    ),
    "analysis_history_date": "SELECT id FROM analysis_history WHERE analysis_date >= '2026-01-01'",
}

_MIGRATION = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "migrations", "versions", "620b1e83d21e_add_hot_path_indexes.py",
)


def _plan(sql: str) -> list[str]:
    with get_session() as s:
        return [str(row[-1]) for row in s.execute(text(f"EXPLAIN QUERY PLAN {sql}")).fetchall()]


@pytest.mark.parametrize("name", sorted(_HOT_QUERIES))
def test_hot_query_uses_index(client, name):
    if database.ENGINE.dialect.name != "sqlite":
        pytest.skip("EXPLAIN QUERY PLAN format is SQLite-specific")
    plan = _plan(_HOT_QUERIES[name])
    assert any("USING" in step and "INDEX" in step for step in plan), plan
    # A bare "SCAN <table>" (no index) is a full table scan; a temp B-tree is a sort.
    assert not any(step.startswith("SCAN") and "INDEX" not in step for step in plan), plan
    assert not any("TEMP B-TREE" in step for step in plan), plan


def test_migration_matches_model_indexes():
    spec = importlib.util.spec_from_file_location("_hot_path_migration", _MIGRATION)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name, table, cols in mod._INDEXES:
        idx = {i.name: i for i in Base.metadata.tables[table].indexes}
        assert name in idx, f"{name} missing from models.{table}"
        assert [c.name for c in idx[name].columns] == cols, name


def test_retention_prunes_only_old_rows(test_user_id, tmp_path, monkeypatch):
    from core import dashboard_state
    from services import retention

    tag = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc)
    old_news, new_news = f"https://example.invalid/{tag}/old", f"https://example.invalid/{tag}/new"
    old_job, new_job = str(uuid.uuid4()), str(uuid.uuid4())
    with get_session() as s:
        for url, age in ((old_news, 100), (new_news, 1)):
            s.add(NewsArticle(source="test", headline=tag, article_url=url,
                              published_at=now - timedelta(days=age)))
        for job_id, age in ((old_job, 40), (new_job, 1)):
            s.add(AnalysisJob(job_id=job_id, ticker="TCS", status="SUCCEEDED",
                              result_json='{"x": 1}', checkpoints='[{"s": 1}]',
                              finished_at=now - timedelta(days=age)))
        old_alert = PriceTarget(user_id=test_user_id, ticker=f"OLD{tag}", target_price=1.0,
                                direction="ABOVE", triggered=True, created_at=now - timedelta(days=100))
        new_alert = PriceTarget(user_id=test_user_id, ticker=f"NEW{tag}", target_price=1.0,
                                direction="ABOVE", triggered=True, created_at=now - timedelta(days=1))
        s.add_all([old_alert, new_alert])
        s.commit()
        old_alert_id, new_alert_id = old_alert.id, new_alert.id

    log = tmp_path / "token_log.jsonl"
    log.write_text("x" * 64)
    monkeypatch.setattr(dashboard_state, "TOKEN_LOG_PATH", str(log))
    monkeypatch.setattr(retention, "TOKEN_LOG_MAX_BYTES", 10)

    try:
        counts = retention.run_retention()

        with get_session() as s:
            urls = {u for (u,) in s.query(NewsArticle.article_url)
                    .filter(NewsArticle.article_url.in_([old_news, new_news]))}
            assert urls == {new_news}
            jobs = {jid: (rj, cp) for jid, rj, cp in s.query(
                        AnalysisJob.job_id, AnalysisJob.result_json, AnalysisJob.checkpoints)
                    .filter(AnalysisJob.job_id.in_([old_job, new_job]))}
            assert set(jobs) == {old_job, new_job}  # rows are kept
            assert jobs[old_job] == (None, "[]")
            assert jobs[new_job] == ('{"x": 1}', '[{"s": 1}]')
            assert s.get(PriceTarget, old_alert_id) is None
            assert s.get(PriceTarget, new_alert_id) is not None

        assert counts["news_deleted"] >= 1 and counts["alerts_deleted"] >= 1
        assert counts["token_log_rotated"] == 1
        assert not log.exists() and (tmp_path / "token_log.jsonl.1").exists()
    finally:
        with get_session() as s:
            s.query(NewsArticle).filter(NewsArticle.article_url.in_([old_news, new_news])).delete(
                synchronize_session=False)
            s.query(AnalysisJob).filter(AnalysisJob.job_id.in_([old_job, new_job])).delete(
                synchronize_session=False)
            s.query(PriceTarget).filter(PriceTarget.id.in_([old_alert_id, new_alert_id])).delete(
                synchronize_session=False)
            s.commit()
