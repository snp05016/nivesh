#!/usr/bin/env bash
# ===========================================================================
# Nivesh Backend Health Check
# Usage: ./scripts/check_backend_health.sh
# Exits 0 only when ALL checks pass.
# ===========================================================================

set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${BACKEND_DIR}/venv/bin/python3"
PYTEST="${BACKEND_DIR}/venv/bin/pytest"
PASS=0
FAIL=0

cd "$BACKEND_DIR"

# Safe test environment — never touch production DB.
# NIVESH_TESTING=1 stops main.py & co. from loading backend/.env over these values.
export NIVESH_TESTING=1
export DATABASE_URL="sqlite:///./stockapp_health_check_test.db"
export ENABLE_SCHEDULER="false"
export JWT_SECRET="health-check-secret-not-for-production"

# Cleanup test DB on exit
cleanup() { rm -f "$BACKEND_DIR/stockapp_health_check_test.db"; }
trap cleanup EXIT

section() { echo; echo "══════════════════════════════════════════"; echo "  $1"; echo "══════════════════════════════════════════"; }
pass() { echo "  ✅ $1"; PASS=$((PASS+1)); }
fail() { echo "  ❌ $1"; FAIL=$((FAIL+1)); }
run_check() {
    local name="$1"; shift
    if "$@" >/dev/null 2>&1; then
        pass "$name"
    else
        fail "$name"
        "$@" 2>&1 | tail -5 || true
    fi
}

# ---------------------------------------------------------------------------
section "1. Python Syntax Check"
# ---------------------------------------------------------------------------
run_check "compileall (syntax)" "$PYTHON" -m compileall -q . 2>/dev/null

# ---------------------------------------------------------------------------
section "2. Linting (ruff)"
# ---------------------------------------------------------------------------
if command -v ruff >/dev/null 2>&1 || "$BACKEND_DIR/venv/bin/ruff" --version >/dev/null 2>&1; then
    RUFF="${BACKEND_DIR}/venv/bin/ruff"
    if "$RUFF" check . --select=E9,F8,F7 -q 2>/dev/null; then
        pass "ruff (fatal errors only)"
    else
        fail "ruff (fatal errors only)"
    fi
else
    echo "  ⚠️  ruff not installed — skipping lint"
fi

# ---------------------------------------------------------------------------
section "3. Import Health"
# ---------------------------------------------------------------------------
run_check "models.db_models import" \
    "$PYTHON" -c "from models.db_models import Base, User, Portfolio, AnalysisHistory, TradeJournal, AnalysisJob; print('ok')"

run_check "database.get_session import" \
    "$PYTHON" -c "from database import get_session, ENGINE; print('ok')"

run_check "schemas.portfolio import" \
    "$PYTHON" -c "from schemas.portfolio import PortfolioAddRequest, TradeJournalAddRequest; print('ok')"

# ---------------------------------------------------------------------------
section "4. Alembic Migration Health"
# ---------------------------------------------------------------------------
run_check "verify_model_migration_drift" \
    "$PYTHON" scripts/verify_model_migration_drift.py

# ---------------------------------------------------------------------------
section "5. Route Registration"
# ---------------------------------------------------------------------------
run_check "verify_route_registration" \
    "$PYTHON" scripts/verify_route_registration.py

# ---------------------------------------------------------------------------
section "6. OpenAPI Schema"
# ---------------------------------------------------------------------------
run_check "validate_openapi" \
    "$PYTHON" scripts/validate_openapi.py

# ---------------------------------------------------------------------------
section "7. Raw SQL Column References"
# ---------------------------------------------------------------------------
run_check "verify_raw_sql_columns" \
    "$PYTHON" scripts/verify_raw_sql_columns.py

# ---------------------------------------------------------------------------
section "8. Regression Test Suite"
# ---------------------------------------------------------------------------
if "$PYTEST" tests/test_database_integrity_fixes.py -q --tb=short 2>/dev/null; then
    pass "DB integrity regression tests (25)"
else
    fail "DB integrity regression tests"
fi

if "$PYTEST" tests/smoke/ -q --tb=short 2>/dev/null; then
    pass "Smoke tests"
else
    fail "Smoke tests"
fi

if "$PYTEST" tests/migrations/ -q --tb=short 2>/dev/null; then
    pass "Migration tests"
else
    fail "Migration tests"
fi

if "$PYTEST" tests/database/ -q --tb=short 2>/dev/null; then
    pass "Database tests"
else
    fail "Database tests"
fi

if "$PYTEST" tests/api/ -q --tb=short 2>/dev/null; then
    pass "API contract tests"
else
    fail "API contract tests"
fi

# ---------------------------------------------------------------------------
section "9. Endpoint Smoke Test"
# ---------------------------------------------------------------------------
run_check "smoke_all_endpoints" \
    "$PYTHON" scripts/smoke_all_endpoints.py

# ---------------------------------------------------------------------------
section "RESULTS"
# ---------------------------------------------------------------------------
echo
echo "  Passed: $PASS"
echo "  Failed: $FAIL"
echo

if [ "$FAIL" -eq 0 ]; then
    echo "  ✅ Backend is HEALTHY"
    exit 0
else
    echo "  ❌ Backend has $FAIL failing check(s)"
    exit 1
fi
