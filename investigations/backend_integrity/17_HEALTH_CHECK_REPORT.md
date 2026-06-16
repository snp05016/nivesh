# Report 17 — Health Check Infrastructure Report

**Date:** 2026-06-16

---

## One-Command Health Check

`backend/scripts/check_backend_health.sh` — runs all verification steps sequentially:

1. Python syntax check (`python -m py_compile` on all .py files)
2. Import health (imports `main` module without error)
3. Alembic drift check (`alembic check`)
4. Route registration (`verify_route_registration.py`)
5. OpenAPI validation (`validate_openapi.py`)
6. Raw SQL column scan (`verify_raw_sql_columns.py`)
7. Pytest smoke suite (`tests/smoke/`)
8. Pytest migration suite (`tests/migrations/`)
9. Pytest DB integrity suite (`tests/db/`)
10. Pytest API contract suite (`tests/api/`)

Uses isolated test DB (`stockapp_health_check_test.db`) and `ENABLE_SCHEDULER=false`.

## Verification Scripts

| Script | Function |
|--------|---------|
| `verify_model_migration_drift.py` | Creates temp DB, runs all migrations, compares ORM metadata vs live schema |
| `verify_route_registration.py` | Enumerates routes, checks for duplicate paths/methods, verifies critical paths |
| `validate_openapi.py` | Generates OpenAPI JSON, checks serializability, counts paths, flags duplicate operationIds |
| `verify_raw_sql_columns.py` | Scans `text()` SQL calls, flags column names not in ORM metadata |
| `smoke_all_endpoints.py` | Hits safe GET endpoints via TestClient, asserts no 500s |
