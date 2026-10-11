"""OPS-03: database backups are written, verified, pruned and scheduled; failures are loud.

Hermetic: temp SQLite files only, Postgres targets disabled, heartbeat HTTP mocked.
"""
import io
import sqlite3
from unittest.mock import MagicMock

import pytest

import services.backup_service as bs


def _make_db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t VALUES (42)")
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def backup_env(tmp_path, monkeypatch):
    """One temp SQLite datastore, a temp BACKUP_DIR, no Postgres, no heartbeat URL."""
    src = _make_db(tmp_path / "live.db")
    monkeypatch.setattr(bs, "BACKUP_DIR", tmp_path / "bk")
    monkeypatch.setattr(bs, "_sqlite_targets", lambda: {"stockapp": src})
    monkeypatch.setattr(bs, "_pg_targets", lambda: {})
    monkeypatch.delenv("BACKUP_HEARTBEAT_URL", raising=False)
    return tmp_path


@pytest.fixture
def http_get(monkeypatch):
    get = MagicMock()
    monkeypatch.setattr(bs.httpx, "get", get)
    return get


def test_sqlite_backup_roundtrip(backup_env, http_get, monkeypatch):
    monkeypatch.setenv("BACKUP_HEARTBEAT_URL", "https://hc.example/check")
    written = bs.run_backup()

    files = sorted((backup_env / "bk").glob("stockapp-*.db"))
    assert files == [written["stockapp"]]
    conn = sqlite3.connect(files[0])
    try:
        assert conn.execute("SELECT x FROM t").fetchall() == [(42,)]
    finally:
        conn.close()
    assert not list((backup_env / "bk").glob("*.partial"))
    assert [c.args[0] for c in http_get.call_args_list] == ["https://hc.example/check"]


def test_prune_keeps_n(backup_env, monkeypatch):
    stamps = iter(["20260101T000001Z", "20260101T000002Z", "20260101T000003Z"])
    monkeypatch.setattr(bs, "_timestamp", lambda: next(stamps))
    monkeypatch.setattr(bs, "KEEP", 2)
    for _ in range(3):
        bs.run_backup()
    names = sorted(p.name for p in (backup_env / "bk").iterdir())
    assert names == ["stockapp-20260101T000002Z.db", "stockapp-20260101T000003Z.db"]


def test_failure_raises_and_pings_fail(backup_env, http_get, monkeypatch):
    not_a_db = backup_env / "garbage.db"
    not_a_db.write_bytes(b"not a database" * 400)
    monkeypatch.setattr(bs, "_sqlite_targets",
                        lambda: {"stockapp": backup_env / "live.db", "harvester": not_a_db})
    monkeypatch.setenv("BACKUP_HEARTBEAT_URL", "https://hc.example/check")

    with pytest.raises(bs.BackupError, match="harvester"):
        bs.run_backup()

    assert http_get.call_args.args[0] == "https://hc.example/check/fail"
    # the healthy datastore was still backed up
    assert len(list((backup_env / "bk").glob("stockapp-*.db"))) == 1


def test_no_heartbeat_when_unset(backup_env, http_get):
    bs.run_backup()
    http_get.assert_not_called()


def test_missing_db_fails_without_creating_it(backup_env, monkeypatch):
    missing = backup_env / "missing.db"
    monkeypatch.setattr(bs, "_sqlite_targets", lambda: {"stockapp": missing})
    with pytest.raises(bs.BackupError):
        bs.run_backup()
    assert not missing.exists()


def test_scheduler_registers_nightly_backup(monkeypatch):
    import fcntl
    import services.harvest_worker as hw

    sched = MagicMock()
    monkeypatch.setattr(hw, "AsyncIOScheduler", lambda **_kw: sched)
    monkeypatch.setattr(hw, "_scheduler", None)
    monkeypatch.setattr(hw, "_scheduler_lock_file", None)
    monkeypatch.setattr(hw, "open", lambda *_a, **_k: io.StringIO(), raising=False)  # no real lock file
    monkeypatch.setattr(fcntl, "lockf", lambda *_a, **_k: None)

    hw.start_scheduler()

    jobs = {c.kwargs.get("id"): c for c in sched.add_job.call_args_list}
    job = jobs["db_backup"]
    assert job.args[1] == "cron" and job.kwargs["hour"] == 21 and job.kwargs["minute"] == 0

    run = MagicMock(return_value={})
    monkeypatch.setattr(bs, "run_backup", run)
    job.args[0]()  # sync job: APScheduler runs it in a worker thread (REL-03)
    run.assert_called_once()
