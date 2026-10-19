"""Deploy one exact commit to the server, with a backup gate and a migration rehearsal (C5).

Run on the server from backend/, after pushing the commit:
    ../venv/bin/python scripts/deploy_server.py --sha <40-hex> [--skip-rehearsal]

Steps (exit code on failure):
  1. Preconditions: tracked files clean, fetch, the commit exists, record prev HEAD (2).
  2. Stage <sha> in a temporary git worktree; the live tree is not touched yet.
  3. pending = the worktree's `alembic heads` differ from the live `alembic current`.
  4. If pending: scripts/backup_db.py in the live tree (3).
  5. If pending (unless --skip-rehearsal): migrate a copy of the fresh backup with the
     worktree's migrations, then `alembic check` (4). The rehearsal uses the live venv,
     so a migration that needs a new dependency fails here. That failure is safe; check
     the migration by hand and re-run with --skip-rehearsal.
  6. Switch the live tree: checkout <sha>, pip install -r requirements.txt (5, rolled back).
  7. If pending: `alembic upgrade head` in the live tree (6, code rolled back, no restart).
  8. Restart nivesh and wait for /health/ready (7, rollback command printed).
Every run appends one JSON line to ~/nivesh-deploys.log. The script never restores a
database automatically and never hard-resets the checkout. See docs/codebase/BACKUP_RESTORE.md.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

LIVE = Path(__file__).resolve().parent.parent  # the backend dir of the live checkout
sys.path.insert(0, str(LIVE))

from sqlalchemy.engine import make_url  # noqa: E402

# Imported before step 6 swaps the code on disk, so rollback paths never import new code.
from services.backup_service import DEFAULT_BACKUP_DIR, libpq_dsn  # noqa: E402

READY_URL = "http://127.0.0.1:8000/health/ready"
READY_POLLS = 30  # every 2 s: 60 s
BACKUP_MAX_AGE_SEC = 15 * 60
PIP = [sys.executable, "-m", "pip", "install", "--quiet", "-r", "requirements.txt"]


def _alembic(*args: str) -> list[str]:
    return [sys.executable, "-m", "alembic", *args]


def _run(cmd: list[str], cwd: Path | str | None = None,
         env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """The only place a subprocess starts (tests replace it)."""
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)


def _secrets() -> list[str]:
    found = []
    for key in ("DATABASE_URL", "RESTORE_DRILL_PG_URL"):
        raw = os.getenv(key)
        if not raw:
            continue
        found.append(raw)
        try:
            dsn, password = libpq_dsn(raw)
            found.append(dsn)
            if password:
                found.append(password)
        except Exception:
            pass
    return sorted(found, key=len, reverse=True)


def _scrub(text: str) -> str:
    for secret in _secrets():
        text = text.replace(secret, "***")
    return text


def _step(label: str, cmd: list[str], cwd: Path | str | None = LIVE,
          env: dict[str, str] | None = None) -> str | None:
    """Run cmd; stdout on success, None (after printing a scrubbed error tail) on failure."""
    proc = _run(cmd, cwd=cwd, env=env)
    if proc.returncode == 0:
        return proc.stdout or ""
    tail = "\n".join(((proc.stderr or "") + (proc.stdout or "")).strip().splitlines()[-20:])
    print(f"FAILED: {label} (exit {proc.returncode})\n{_scrub(tail)}", file=sys.stderr)
    return None


def _revisions(out: str) -> set[str]:
    return {line.split()[0] for line in out.splitlines() if line.strip()}


def _backup_dir() -> Path:
    return Path(os.getenv("BACKUP_DIR", DEFAULT_BACKUP_DIR)).expanduser()


def _fresh_backup() -> Path | None:
    """The newest finished main-DB backup written in the last 15 minutes."""
    now = time.time()
    copies = [p for p in _backup_dir().glob("stockapp-*")
              if not p.name.endswith(".partial") and now - p.stat().st_mtime <= BACKUP_MAX_AGE_SEC]
    return max(copies, key=lambda p: p.stat().st_mtime, default=None)


def _same_database(a: str, b: str) -> bool:
    """True when a and b name the same Postgres database, or either cannot be parsed."""
    try:
        ua, ub = make_url(a), make_url(b)
    except Exception:
        return True
    return (ua.host, ua.port or 5432, ua.database) == (ub.host, ub.port or 5432, ub.database)


def _rehearse(stage: Path, backup: Path, state: dict) -> bool:
    """Migrate a copy of `backup` with the staged commit's migrations; True on success."""
    def migrate(url: str) -> bool:
        env = dict(os.environ, DATABASE_URL=url)
        return (_step("rehearsal alembic upgrade head", _alembic("upgrade", "head"), cwd=stage, env=env) is not None
                and _step("rehearsal alembic check", _alembic("check"), cwd=stage, env=env) is not None)

    if backup.suffix == ".db":
        state["rehearsal"] = "sqlite"
        with tempfile.TemporaryDirectory(prefix="nivesh-rehearsal-") as scratch:
            copy = Path(scratch) / backup.name
            shutil.copy2(backup, copy)
            return migrate(f"sqlite:///{copy}")

    state["rehearsal"] = "postgres"
    scratch_url = os.getenv("RESTORE_DRILL_PG_URL", "")
    if not scratch_url:
        print("REHEARSAL: RESTORE_DRILL_PG_URL (a scratch Postgres DB) is not set", file=sys.stderr)
        return False
    if _same_database(scratch_url, os.getenv("DATABASE_URL", "")):
        print("REHEARSAL: RESTORE_DRILL_PG_URL names the live database; refusing", file=sys.stderr)
        return False
    dsn, password = libpq_dsn(scratch_url)
    env = dict(os.environ)
    env.pop("PGPASSWORD", None)
    if password:
        env["PGPASSWORD"] = password
    restore = ["pg_restore", "--clean", "--if-exists", "--no-owner", "--dbname", dsn, str(backup)]
    if _step("rehearsal pg_restore into the scratch DB", restore, env=env) is None:
        return False
    return migrate(scratch_url)


def _restore_steps(backup: str) -> str:
    return (
        f"Backup taken before this migration: {backup}\n"
        "A restore is needed only if `../venv/bin/python -m alembic current` no longer shows the\n"
        "previous revision (Postgres rolls back failed DDL; SQLite may not). To restore, follow\n"
        "docs/codebase/BACKUP_RESTORE.md, section Restore:\n"
        "  sudo systemctl stop nivesh\n"
        f"  SQLite: move stockapp.db, -wal and -shm aside, cp {backup} stockapp.db, PRAGMA integrity_check\n"
        f"  Postgres: PGPASSWORD=... pg_restore --clean --if-exists --no-owner --dbname <libpq DSN> {backup}\n"
        "  sudo systemctl start nivesh"
    )


def _ready() -> bool:
    for attempt in range(READY_POLLS):
        try:
            with urllib.request.urlopen(READY_URL, timeout=5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass  # 503 (HTTPError), refused while starting, timeout
        if attempt < READY_POLLS - 1:
            time.sleep(2)
    return False


def _rollback_code(prev: str) -> None:
    """Put the live tree back on prev with prev's requirements (the process still serves prev)."""
    _step("checkout prev", ["git", "checkout", "--quiet", "--detach", prev])
    _step("pip install prev requirements", PIP)


def _deploy(sha: str, skip_rehearsal: bool, state: dict) -> int:
    # 1. Preconditions. Untracked logs and local DBs never block.
    dirty = _step("git status", ["git", "status", "--porcelain", "--untracked-files=no"])
    if dirty is None:
        return 2
    if dirty.strip():
        print(f"ABORT: tracked files changed on the server:\n{dirty}", file=sys.stderr)
        return 2
    if _step("git fetch", ["git", "fetch", "--quiet", "origin"]) is None:
        return 2
    if _step(f"commit {sha} exists", ["git", "cat-file", "-e", f"{sha}^{{commit}}"]) is None:
        return 2
    prev = _step("git rev-parse HEAD", ["git", "rev-parse", "HEAD"])
    if prev is None:
        return 2
    prev = prev.strip()
    state["prev_sha"] = prev

    # 2. Stage the commit outside the repo; the live tree is untouched until step 6.
    tmp = Path(tempfile.mkdtemp(prefix="nivesh-deploy-"))
    try:
        if _step("git worktree add", ["git", "worktree", "add", "--detach", str(tmp), sha]) is None:
            return 2
        stage = tmp / "backend"

        # 3. Pending migrations?
        heads = _step("alembic heads (staged)", _alembic("heads"), cwd=stage)
        current = _step("alembic current (live)", _alembic("current"))
        if heads is None or current is None:
            return 2
        pending = _revisions(heads) != _revisions(current)

        # 4. Backup gate.
        backup_name = "<newest stockapp-* in BACKUP_DIR>"
        if pending:
            if _step("backup_db.py", [sys.executable, "scripts/backup_db.py"]) is None:
                print("BACKUP FAILED: nothing was changed", file=sys.stderr)
                return 3
            backup = _fresh_backup()
            if backup is not None:
                backup_name = str(backup)

            # 5. Rehearsal on a copy of the backup.
            if skip_rehearsal:
                state["rehearsal"] = "skipped"
            else:
                if backup is None:
                    print("REHEARSAL: no stockapp-* backup from the last 15 minutes", file=sys.stderr)
                    return 4
                if not _rehearse(stage, backup, state):
                    print("REHEARSAL FAILED: the live tree was not touched", file=sys.stderr)
                    return 4
    finally:
        _run(["git", "worktree", "remove", "--force", str(tmp)], cwd=LIVE)
        shutil.rmtree(tmp, ignore_errors=True)

    # 6. Switch the live tree, only now.
    if (_step("checkout sha", ["git", "checkout", "--quiet", "--detach", sha]) is None
            or _step("pip install requirements", PIP) is None):
        _rollback_code(prev)
        print(f"ABORT: switch failed; checked out {prev} again", file=sys.stderr)
        return 5

    # 7. Production migration. The service has not restarted, so it still serves prev.
    if pending:
        if _step("alembic upgrade head (live)", _alembic("upgrade", "head")) is None:
            _rollback_code(prev)
            print(f"MIGRATION FAILED: code is back on {prev}; nivesh was not restarted.\n"
                  f"{_restore_steps(backup_name)}", file=sys.stderr)
            return 6
        state["migrated"] = True

    # 8. Restart under systemd and wait for readiness.
    restarted = _step("systemctl restart nivesh", ["sudo", "systemctl", "restart", "nivesh"]) is not None
    if not (restarted and _ready()):
        print("NOT READY: /health/ready did not return 200 within 60 s. Roll back with:", file=sys.stderr)
        if state["migrated"]:
            print(f"  restore {backup_name} first (see docs/codebase/BACKUP_RESTORE.md)", file=sys.stderr)
        print(f"  git checkout --detach {prev} && ../venv/bin/pip install -r requirements.txt"
              " && sudo systemctl restart nivesh", file=sys.stderr)
        return 7
    print(f"DEPLOYED {sha} (previous {prev})")
    return 0


def _sha(value: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", value):
        raise argparse.ArgumentTypeError("must be a full 40-character commit SHA")
    return value.lower()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sha", required=True, type=_sha)
    parser.add_argument("--skip-rehearsal", action="store_true")
    args = parser.parse_args(argv)

    state = {"sha": args.sha, "prev_sha": None, "migrated": False, "rehearsal": "none"}
    code = 1  # an unexpected exception
    try:
        from core.env import load_backend_env  # python-dotenv, override=False

        load_backend_env()
        code = _deploy(args.sha, args.skip_rehearsal, state)
        return code
    finally:
        line = {"ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), **state, "exit_code": code}
        try:
            with open(Path.home() / "nivesh-deploys.log", "a") as log:
                log.write(json.dumps(line) + "\n")
        except OSError as e:
            print(f"could not write ~/nivesh-deploys.log: {e}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
