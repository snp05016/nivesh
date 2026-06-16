#!/usr/bin/env bash
# run_integrity_tests.sh
# ======================
# Convenience script to run BOTH test suites on the server.
# Run from: /home/saumyapatel/Desktop/nivesh/backend
#
# Usage:
#   ssh saumyapatel@192.168.1.122 "cd /home/saumyapatel/Desktop/nivesh/backend && bash tests/run_integrity_tests.sh"

set -euo pipefail

VENV_PYTHON="../venv/bin/python"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================================"
echo "  NIVESH INTEGRITY TEST SUITE"
echo "  Backend: $BACKEND_DIR"
echo "  Python:  $($VENV_PYTHON --version)"
echo "  Date:    $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "========================================================"

DB_PASS=0
DB_FAIL=0
BE_PASS=0
BE_FAIL=0

echo ""
echo "--- [1/2] DATABASE INTEGRITY TESTS ---"
if timeout 300 "$VENV_PYTHON" tests/database_integrity_tests/run_all.py; then
    DB_PASS=1
    echo "[OK] Database integrity tests PASSED"
else
    DB_FAIL=1
    echo "[FAIL] Database integrity tests FAILED"
fi

echo ""
echo "--- [2/2] BACKEND INTEGRITY TESTS ---"
if timeout 300 "$VENV_PYTHON" tests/backend_integrity_tests/run_all.py; then
    BE_PASS=1
    echo "[OK] Backend integrity tests PASSED"
else
    BE_FAIL=1
    echo "[FAIL] Backend integrity tests FAILED"
fi

echo ""
echo "========================================================"
echo "  FINAL RESULT"
echo "  Database: $([ $DB_FAIL -eq 0 ] && echo 'PASS' || echo 'FAIL')"
echo "  Backend : $([ $BE_FAIL -eq 0 ] && echo 'PASS' || echo 'FAIL')"
echo "  Logs: tests/database_integrity_tests/logs/"
echo "        tests/backend_integrity_tests/logs/"
echo "========================================================"

if [ $DB_FAIL -ne 0 ] || [ $BE_FAIL -ne 0 ]; then
    exit 1
fi
exit 0
