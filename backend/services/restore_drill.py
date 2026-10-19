"""Monthly restore drill: prove last night's main-database backup restores and holds the data.

SQLite backups are copied to a temp directory, integrity-checked and counted. Postgres
dumps are always listed with pg_restore; only when RESTORE_DRILL_PG_URL names an empty
scratch database (name contains 'drill' or 'scratch', never a live database) is the dump
restored into it and counted. Targets are validated before any subprocess runs, and URLs
and passwords are never logged. Scheduled by harvest_worker (id restore_drill); by hand:
scripts/restore_drill.py.
"""
import logging
import os
import shutil
import sqlite3
import subprocess
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url

from database import get_session
from services import backup_service

logger = logging.getLogger(__name__)

MAIN_TARGET = "stockapp"
DRILL_TABLES = (
    "users", "portfolio", "portfolio_transactions", "kyc_consents",
    "audit_log_entries", "research_predictions", "job_runs",
)
_MUST_NOT_BE_EMPTY = ("users", "portfolio_transactions")
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
LIST_TIMEOUT_SEC = 300
RESTORE_TIMEOUT_SEC = 3600


class RestoreDrillFailed(RuntimeError):
    """The restore drill found a problem with the backup."""


def _latest_backup() -> Path:
    candidates = [
        p for p in backup_service.BACKUP_DIR.glob(f"{MAIN_TARGET}-*")
        if not p.name.endswith(".partial")
    ]
    if not candidates:
        raise RestoreDrillFailed("no backup found")
    return sorted(candidates)[-1]  # the UTC timestamp in the name sorts by age


def _age_hours(path: Path) -> float:
    try:
        stamp = path.name.split("-", 1)[1].split(".", 1)[0]
        written = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except (IndexError, ValueError):
        written = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    return round((datetime.now(timezone.utc) - written).total_seconds() / 3600, 1)


def _norm_target(url: URL) -> tuple[str, int, str]:
    host = (url.host or "localhost").lower()
    if host in _LOCAL_HOSTS:
        host = "localhost"
    return host, url.port or 5432, (url.database or "").lower()


def _check_scratch_target(url: str) -> None:
    """Refuse anything but an empty-by-convention scratch database. Never echoes the URL."""
    try:
        target = make_url(url)
    except Exception:
        raise ValueError("RESTORE_DRILL_PG_URL is not a valid database URL") from None
    name = (target.database or "").lower()
    if "drill" not in name and "scratch" not in name:
        raise ValueError("RESTORE_DRILL_PG_URL database name must contain drill or scratch")
    wanted = _norm_target(target)
    for env_name, value in os.environ.items():
        if env_name != "DATABASE_URL" and not env_name.endswith("_DATABASE_URL"):
            continue
        try:
            other = _norm_target(make_url(value))
        except Exception:
            continue
        if other == wanted:
            raise ValueError(f"scratch URL points at the database in {env_name}")


def _count_sqlite(path: str) -> dict[str, int]:
    with closing(sqlite3.connect(path)) as conn:
        present = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in DRILL_TABLES if t in present}


def _count_pg(url: str) -> dict[str, int]:
    engine = create_engine(url)
    try:
        present = set(inspect(engine).get_table_names())
        with engine.connect() as conn:
            return {
                t: conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar_one()
                for t in DRILL_TABLES if t in present
            }
    finally:
        engine.dispose()


def _count_live() -> dict[str, int]:
    out: dict[str, int] = {}
    with get_session() as session:
        present = set(inspect(session.get_bind()).get_table_names())
        for t in DRILL_TABLES:
            if t in present:
                out[t] = session.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar_one()
    return out


def _compare(backup: dict[str, int], live: dict[str, int]) -> dict[str, dict]:
    tables = {t: {"backup": backup[t], "live": live[t]} for t in DRILL_TABLES if t in backup and t in live}
    problems = []
    for t, c in tables.items():
        if c["live"] >= 100 and c["backup"] < 0.5 * c["live"]:
            problems.append(f"{t} has {c['backup']} rows in the backup vs {c['live']} live")
        elif t in _MUST_NOT_BE_EMPTY and c["live"] > 0 and c["backup"] == 0:
            problems.append(f"{t} is empty in the backup but has {c['live']} rows live")
    if problems:
        raise RestoreDrillFailed("; ".join(problems))
    return tables


def _drill_sqlite(path: Path) -> dict[str, int]:
    with tempfile.TemporaryDirectory(prefix="nivesh-drill-") as tmp:
        copy = Path(tmp) / "restore.db"
        shutil.copyfile(path, copy)
        try:
            with closing(sqlite3.connect(copy)) as conn:
                check = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if check != "ok":
                raise RestoreDrillFailed(f"integrity_check failed: {str(check)[:100]}")
            return _count_sqlite(str(copy))
        except sqlite3.DatabaseError as exc:
            raise RestoreDrillFailed(f"backup is not a readable SQLite file: {type(exc).__name__}") from None


def _run(cmd: list[str], timeout: int) -> None:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RestoreDrillFailed(f"{cmd[0]} timed out") from None
    if proc.returncode != 0:
        # stderr can quote the connection string; keep only the tail of the first line of text.
        raise RestoreDrillFailed(f"{cmd[0]} exited {proc.returncode}")


def _drill_postgres(path: Path) -> tuple[str, Optional[dict[str, int]]]:
    scratch = os.getenv("RESTORE_DRILL_PG_URL", "").strip()
    if scratch:
        _check_scratch_target(scratch)  # before any subprocess
    if shutil.which("pg_restore") is None:
        raise RestoreDrillFailed("pg_restore not installed")
    _run(["pg_restore", "--list", str(path)], LIST_TIMEOUT_SEC)
    if not scratch:
        return "listed_only", None
    _run(["pg_restore", "--clean", "--if-exists", "--no-owner", "--dbname", scratch, str(path)],
         RESTORE_TIMEOUT_SEC)
    return "ok", _count_pg(scratch)


def run_restore_drill(backup_path: Optional[str] = None) -> dict:
    path = Path(backup_path) if backup_path else _latest_backup()
    if not path.is_file():
        raise RestoreDrillFailed("no backup found")
    if path.suffix == ".db":
        status, counts = "ok", _drill_sqlite(path)
    else:
        status, counts = _drill_postgres(path)
    tables = _compare(counts, _count_live()) if counts is not None else {}
    result = {"status": status, "backup": path.name, "age_hours": _age_hours(path), "tables": tables}
    logger.info("[restore_drill] %s: %s", path.name, status)
    return result
