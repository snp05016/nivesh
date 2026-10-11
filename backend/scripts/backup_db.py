"""Back up every Nivesh datastore now. Run it before any server migration (OPS-03).

Run from backend/; a failed backup exits 1, so the && stops the migration:
    ../venv/bin/python scripts/backup_db.py && ../venv/bin/alembic upgrade head

Copies go to BACKUP_DIR (default ~/nivesh-backups). See docs/codebase/BACKUP_RESTORE.md.
"""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


def main() -> int:
    # Same cwd as the service (WorkingDirectory=backend), so a relative sqlite DATABASE_URL
    # names the same file. override=False: a DATABASE_URL exported in this shell is also
    # what alembic will migrate, so that is the database to back up.
    os.chdir(BACKEND)
    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env", override=False)
    from services.backup_service import BackupError, run_backup  # reads BACKUP_* at import

    try:
        written = run_backup()
    except BackupError as e:
        print(f"BACKUP FAILED, do not migrate: {e}", file=sys.stderr)
        return 1
    for name, path in written.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
