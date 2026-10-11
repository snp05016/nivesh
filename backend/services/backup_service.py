"""Backups of every datastore the backend uses (OPS-03).

Runs nightly from the APScheduler (harvest_worker.start_scheduler) and by hand through
scripts/backup_db.py before any server migration. Copies go to BACKUP_DIR, which must sit
outside the git checkout so `git reset --hard` / `git clean` cannot delete them:

- SQLite (the main DB when DATABASE_URL is sqlite, plus harvester.db): SQLite's online
  backup API, safe while the app is writing under WAL. Each copy must pass PRAGMA quick_check.
- PostgreSQL (the main DB when DATABASE_URL is postgresql, plus the RAG pgvector DB when
  RAG_DB_PASS is set): pg_dump --format=custom. Passwords travel in PGPASSWORD, never argv.

The newest BACKUP_KEEP copies of each datastore are kept. BACKUP_HEARTBEAT_URL
(healthchecks.io style) is pinged on success and <url>/fail on failure, so a failed or
missed night raises an alert. The off-host copy is a server crontab job; restore steps
are in docs/codebase/BACKUP_RESTORE.md.
"""
import logging
import os
import sqlite3
import subprocess
from contextlib import closing
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "~/nivesh-backups")).expanduser()
KEEP = max(1, int(os.getenv("BACKUP_KEEP", "14")))  # never 0: pruning must keep the copy just made
PG_DUMP_TIMEOUT_SEC = 30 * 60


class BackupError(RuntimeError):
    """At least one datastore could not be backed up."""


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sqlite_targets() -> dict[str, Path]:
    import database
    from sqlalchemy.engine import make_url
    from services.harvester_db import _DB_PATH as harvester_db

    targets: dict[str, Path] = {}
    if database.DATABASE_URL.startswith("sqlite"):
        # A relative path resolves against the cwd, as in SQLAlchemy. A missing main DB
        # is deliberately not skipped: _backup_sqlite fails on it, loudly.
        targets["stockapp"] = Path(str(make_url(database.DATABASE_URL).database))
    if harvester_db.exists():
        targets["harvester"] = harvester_db
    return targets


def _pg_targets() -> dict[str, tuple[list[str], str | None]]:
    """name -> (pg_dump connection args without the password, password)."""
    import database
    from sqlalchemy.engine import make_url

    targets: dict[str, tuple[list[str], str | None]] = {}
    if database.DATABASE_URL.startswith("postgresql"):
        url = make_url(database.DATABASE_URL)
        # libpq rejects driver suffixes such as postgresql+psycopg2://
        dsn = url._replace(password=None).set(drivername="postgresql").render_as_string(hide_password=False)
        targets["stockapp"] = (["--dbname", dsn], url.password)
    rag_password = os.getenv("RAG_DB_PASS")
    if rag_password:  # same settings and defaults as services/vector_store.py
        targets["rag"] = ([
            "--host", os.getenv("RAG_DB_HOST", "127.0.0.1"),
            "--username", os.getenv("RAG_DB_USER", "saumyapatel"),
            "--dbname", os.getenv("RAG_DB_NAME", "nivesh"),
        ], rag_password)
    return targets


def _backup_sqlite(src: Path, dest: Path) -> None:
    tmp = dest.with_name(dest.name + ".partial")
    tmp.unlink(missing_ok=True)
    try:
        # mode=ro: never write to the live DB, and fail instead of creating an empty one.
        with closing(sqlite3.connect(src.resolve().as_uri() + "?mode=ro", uri=True)) as src_conn:
            with closing(sqlite3.connect(tmp)) as dst_conn:
                src_conn.backup(dst_conn)
                check = dst_conn.execute("PRAGMA quick_check").fetchone()[0]
        if check != "ok":
            raise BackupError(f"quick_check failed on the copy of {src.name}: {check}")
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    os.replace(tmp, dest)


def _backup_pg(dest: Path, conn_args: list[str], password: str | None) -> None:
    tmp = dest.with_name(dest.name + ".partial")
    env = dict(os.environ)
    if password:
        env["PGPASSWORD"] = password
    try:
        proc = subprocess.run(
            ["pg_dump", "--format=custom", "--file", str(tmp), *conn_args],
            env=env, capture_output=True, text=True, timeout=PG_DUMP_TIMEOUT_SEC,
        )
        if proc.returncode != 0:
            raise BackupError(f"pg_dump exited {proc.returncode}: {proc.stderr.strip()[-500:]}")
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    os.replace(tmp, dest)


def _prune(name: str) -> None:
    """Delete all but the newest KEEP copies; the UTC timestamp in the name sorts by age."""
    copies = sorted(p for p in BACKUP_DIR.glob(f"{name}-*") if not p.name.endswith(".partial"))
    for old in copies[:-KEEP]:
        old.unlink(missing_ok=True)


def _heartbeat(ok: bool) -> None:
    url = os.getenv("BACKUP_HEARTBEAT_URL", "").strip()
    if not url:
        return
    try:
        httpx.get(url if ok else url.rstrip("/") + "/fail", timeout=10).raise_for_status()
    except Exception as e:
        logger.warning("[db_backup] heartbeat ping failed: %s", type(e).__name__)  # the URL is a secret


def run_backup() -> dict[str, Path]:
    """Back up every datastore; return {name: backup file}.

    Targets are independent: one failure does not stop the others. Raises BackupError
    naming every failed target (or when no datastore was found) after trying them all.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp()
    jobs = [(name, ".db", partial(_backup_sqlite, src)) for name, src in _sqlite_targets().items()]
    jobs += [(name, ".dump", partial(_backup_pg, conn_args=args, password=pw))
             for name, (args, pw) in _pg_targets().items()]
    written: dict[str, Path] = {}
    failed = [] if jobs else ["(no datastore found)"]
    for name, suffix, backup in jobs:
        dest = BACKUP_DIR / f"{name}-{stamp}{suffix}"
        try:
            backup(dest)
            _prune(name)
            written[name] = dest
            logger.info("[db_backup] %s -> %s", name, dest)
        except Exception as e:
            failed.append(name)
            logger.error("[db_backup] %s failed: %s", name, e)
    _heartbeat(ok=not failed)
    if failed:
        raise BackupError(f"backup failed for: {', '.join(failed)}")
    return written
