"""Run the restore drill now (I48): restores the newest main-database backup into a scratch
location and compares row counts with the live database.

Run from backend/:
    ../venv/bin/python scripts/restore_drill.py [--backup PATH]

The run is recorded in job_runs (job 'restore_drill') and a failure alerts through
OPS_ALERT_WEBHOOK_URL. Exits 1 on any failure. See docs/codebase/BACKUP_RESTORE.md.
"""
import argparse
import json
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backup", help="restore this backup file instead of the newest one")
    args = parser.parse_args(argv)

    os.chdir(BACKEND)
    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env", override=False)
    from services.job_runs import tracked
    from services.restore_drill import run_restore_drill

    try:
        result = tracked("restore_drill", run_restore_drill)(args.backup)
    except Exception as exc:
        print(f"RESTORE DRILL FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
