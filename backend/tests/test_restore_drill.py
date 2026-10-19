"""services/restore_drill: SQLite checks, scratch-target guards, CLI job_runs row."""
import sqlite3
import subprocess

import pytest

from database import ENGINE, get_session
from models.db_models import JobRun
from services import backup_service, restore_drill
from services.restore_drill import RestoreDrillFailed


def _make_db(path, users=3, txns=2):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE users (id INTEGER)")
    conn.execute("CREATE TABLE portfolio_transactions (id INTEGER)")
    conn.executemany("INSERT INTO users VALUES (?)", [(i,) for i in range(users)])
    conn.executemany("INSERT INTO portfolio_transactions VALUES (?)", [(i,) for i in range(txns)])
    conn.commit()
    conn.close()


@pytest.fixture
def backups(tmp_path, monkeypatch):
    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path)
    monkeypatch.setattr(restore_drill, "_count_live", lambda: {"users": 3, "portfolio_transactions": 2})
    return tmp_path


@pytest.fixture
def no_subprocess(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("subprocess must not run")

    monkeypatch.setattr(subprocess, "run", fail)


def test_healthy_backup(backups):
    _make_db(backups / "stockapp-20261001T020000Z.db")
    out = restore_drill.run_restore_drill()
    assert out["status"] == "ok" and out["backup"] == "stockapp-20261001T020000Z.db"
    assert out["tables"]["users"] == {"backup": 3, "live": 3}
    assert isinstance(out["age_hours"], float)


def test_newest_backup_wins_and_other_targets_ignored(backups):
    _make_db(backups / "stockapp-20260901T020000Z.db", users=0)
    _make_db(backups / "stockapp-20261001T020000Z.db")
    (backups / "harvester-20261002T020000Z.db").write_bytes(b"x")
    assert restore_drill.run_restore_drill()["backup"] == "stockapp-20261001T020000Z.db"


def test_emptied_users_fails(backups):
    _make_db(backups / "stockapp-20261001T020000Z.db", users=0)
    with pytest.raises(RestoreDrillFailed, match="users"):
        restore_drill.run_restore_drill()


def test_truncated_backup_fails(backups, monkeypatch):
    _make_db(backups / "stockapp-20261001T020000Z.db", users=10)
    monkeypatch.setattr(restore_drill, "_count_live", lambda: {"users": 300, "portfolio_transactions": 2})
    with pytest.raises(RestoreDrillFailed, match="vs 300 live"):
        restore_drill.run_restore_drill()


def test_corrupt_file_fails(backups):
    (backups / "stockapp-20261001T020000Z.db").write_bytes(b"not a database" * 100)
    with pytest.raises(RestoreDrillFailed):
        restore_drill.run_restore_drill()


def test_no_backup_fails(backups):
    with pytest.raises(RestoreDrillFailed, match="no backup found"):
        restore_drill.run_restore_drill()


@pytest.fixture
def pg_backup(backups, monkeypatch):
    (backups / "stockapp-20261001T020000Z.dump").write_bytes(b"PGDMP")
    monkeypatch.setattr(restore_drill.shutil, "which", lambda name: "/usr/bin/pg_restore")


def test_scratch_name_must_contain_drill_or_scratch(pg_backup, monkeypatch, no_subprocess):
    monkeypatch.setenv("RESTORE_DRILL_PG_URL", "postgresql://u:secret@db.example/nivesh")
    with pytest.raises(ValueError, match="drill or scratch") as exc:
        restore_drill.run_restore_drill()
    assert "secret" not in str(exc.value)


def test_scratch_equal_to_database_url_refused(pg_backup, monkeypatch, no_subprocess):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/nivesh_drill")
    monkeypatch.setenv("RESTORE_DRILL_PG_URL", "postgresql://x:y@127.0.0.1:5432/nivesh_drill")
    with pytest.raises(ValueError, match="DATABASE_URL"):
        restore_drill.run_restore_drill()


def test_scratch_equal_to_other_database_url_refused(pg_backup, monkeypatch, no_subprocess):
    monkeypatch.setenv("HARVESTER_DATABASE_URL", "postgresql://u:p@localhost/scratch_h")
    monkeypatch.setenv("RESTORE_DRILL_PG_URL", "postgresql://x:y@127.0.0.1:5432/scratch_h")
    with pytest.raises(ValueError, match="HARVESTER_DATABASE_URL"):
        restore_drill.run_restore_drill()


def test_missing_pg_restore(pg_backup, monkeypatch):
    monkeypatch.delenv("RESTORE_DRILL_PG_URL", raising=False)
    monkeypatch.setattr(restore_drill.shutil, "which", lambda name: None)
    with pytest.raises(RestoreDrillFailed, match="pg_restore not installed"):
        restore_drill.run_restore_drill()


def test_listed_only_without_scratch_url(pg_backup, backups, monkeypatch):
    monkeypatch.delenv("RESTORE_DRILL_PG_URL", raising=False)
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **k: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0, "", ""))
    out = restore_drill.run_restore_drill()
    assert out["status"] == "listed_only" and calls == [["pg_restore", "--list", str(backups / "stockapp-20261001T020000Z.dump")]]


def test_full_restore_into_scratch(pg_backup, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db.example/live")
    monkeypatch.setenv("RESTORE_DRILL_PG_URL", "postgresql://x:y@scratchhost/nivesh_restore_drill")
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **k: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0, "", ""))
    monkeypatch.setattr(restore_drill, "_count_pg", lambda url: {"users": 3, "portfolio_transactions": 2})
    out = restore_drill.run_restore_drill()
    assert out["status"] == "ok" and len(calls) == 2 and "--clean" in calls[1]


def test_cli_records_failed_job_run(backups, monkeypatch, capsys):
    import importlib.util
    from pathlib import Path
    from services import job_runs

    JobRun.__table__.create(ENGINE, checkfirst=True)
    alerts = []
    monkeypatch.setattr(job_runs, "notify_ops", lambda t, b: alerts.append((t, b)) or True)
    spec = importlib.util.spec_from_file_location(
        "restore_drill_cli", Path(__file__).resolve().parent.parent / "scripts" / "restore_drill.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    monkeypatch.chdir(Path(__file__).resolve().parent)  # the CLI chdirs; restored by monkeypatch
    with get_session() as s:
        s.query(JobRun).filter(JobRun.job_name == "restore_drill").delete()
        s.commit()
    assert cli.main([]) == 1  # empty BACKUP_DIR -> no backup found
    with get_session() as s:
        row = s.query(JobRun).filter(JobRun.job_name == "restore_drill").one()
        assert row.status == "failed" and "no backup found" in row.error
        s.delete(row)
        s.commit()
    assert alerts and alerts[0][0] == "Nivesh job failed: restore_drill"
