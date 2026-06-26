import logging
"""
database_integrity_tests/run_all.py
====================================
Master runner for the Nivesh database integrity test suite.

Usage (on server):
    cd /home/saumyapatel/Desktop/nivesh/backend
    ../venv/bin/python tests/database_integrity_tests/run_all.py

Produces:
    tests/database_integrity_tests/logs/db_integrity_YYYY-MM-DD_HH-MM-SS.txt
"""
import sys
import os
import subprocess
import datetime
import traceback
from pathlib import Path

HERE   = Path(__file__).parent
LOGS   = HERE / "logs"
LOGS.mkdir(exist_ok=True)

TS      = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = LOGS / f"db_integrity_{TS}.txt"

# The modules to run (in order)
MODULES = [
    "test_01_schema_columns.py",
    "test_02_constraints.py",
    "test_03_relationships.py",
    "test_04_migration_drift.py",
    "test_05_crud_lifecycle.py",
    "test_06_session_management.py",
    "test_07_concurrent_writes.py",
    "test_08_null_enforcement.py",
    "test_09_foreign_keys.py",
    "test_10_unique_constraints.py",
    "test_11_check_constraints.py",
    "test_12_indexes.py",
    "test_13_telemetry_tables.py",
    "test_14_seed_data.py",
    "test_15_error_recovery.py",
]

PYTHON = sys.executable


def run_module(module: str, log_fh) -> bool:
    path = HERE / module
    log_fh.write(f"\n{'='*70}\n")
    log_fh.write(f"  MODULE: {module}\n")
    log_fh.write(f"  STARTED: {datetime.datetime.now().isoformat()}\n")
    log_fh.write(f"{'='*70}\n")
    log_fh.flush()

    try:
        result = subprocess.run(
            [PYTHON, str(path)],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "PYTHONPATH": str(HERE.parent.parent)},
        )
        log_fh.write(result.stdout)
        if result.stderr:
            log_fh.write("\n--- STDERR ---\n")
            log_fh.write(result.stderr)
        log_fh.write(f"\n  EXIT CODE: {result.returncode}\n")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log_fh.write(f"\n  [TIMEOUT] {module} exceeded 120s\n")
        return False
    except Exception as exc:
        log_fh.write(f"\n  [RUNNER ERROR] {exc}\n")
        log_fh.write(traceback.format_exc())
        return False


def main():
    passed = []
    failed = []

    with open(LOG_FILE, "w") as fh:
        fh.write("=" * 70 + "\n")
        fh.write("NIVESH DATABASE INTEGRITY TEST SUITE\n")
        fh.write(f"Run timestamp : {datetime.datetime.now().isoformat()}\n")
        fh.write(f"Python        : {sys.version}\n")
        fh.write(f"Working dir   : {os.getcwd()}\n")
        fh.write("=" * 70 + "\n")

        for mod in MODULES:
            ok = run_module(mod, fh)
            if ok:
                passed.append(mod)
            else:
                failed.append(mod)

        fh.write("\n" + "=" * 70 + "\n")
        fh.write("SUMMARY\n")
        fh.write("=" * 70 + "\n")
        fh.write(f"PASSED ({len(passed)}): {', '.join(passed) or 'none'}\n")
        fh.write(f"FAILED ({len(failed)}): {', '.join(failed) or 'none'}\n")
        fh.write(f"Finished: {datetime.datetime.now().isoformat()}\n")

    logging.info(f"\n[runner] Log written → {LOG_FILE}")
    logging.info(f"[runner] {len(passed)} passed / {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
