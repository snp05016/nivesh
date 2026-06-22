# Migration Fix Report — Missing Columns

**Date:** 2026-06-16  
**Agent:** Migration Fix Agent  
**Status:** COMPLETE

---

## Migration File Created

**Filename:** `backend/migrations/versions/a1b2c3d4e5f6_add_missing_columns.py`  
**Revision ID:** `a1b2c3d4e5f6`  
**Down-revision:** `1ad82d60efcc` (previous head)

---

## Tables Affected

### 1. `trade_journal` — 3 columns added

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `company_name` | `VARCHAR(200)` | Yes | Company display name |
| `mood` | `VARCHAR(30)` | Yes | Trader sentiment at entry time |
| `updated_at` | `DateTime` | Yes | Last update timestamp |

### 2. `analysis_history` — 10 columns added

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `outcome_delta_pct` | `Float` | Yes | NULL | % price change since analysis |
| `was_correct` | `Boolean` | Yes | NULL | Signal matched price direction |
| `outcome_checked_at` | `DateTime` | Yes | NULL | When outcome was evaluated |
| `market_regime` | `String` | Yes | NULL | Market regime at analysis time |
| `calibrated_confidence` | `Float` | Yes | `0.0` | ML-adjusted confidence score |
| `confidence_math_breakdown` | `JSON` | Yes | `{}` | Calibration calculation detail |
| `conformal_target_upper_3m` | `Float` | Yes | NULL | Conformal upper bound (3-month) |
| `conformal_target_lower_3m` | `Float` | Yes | NULL | Conformal lower bound (3-month) |
| `quantitative_drivers` | `JSON` | Yes | `{}` | Quantitative signal drivers |
| `tail_risk_flags` | `JSON` | Yes | `{}` | Tail risk indicators |

---

## Migration Design Notes

### Idempotent Design (key fix)

The initial migration version crashed with `OperationalError: duplicate column name: company_name` because `stockapp.db` already had these columns added by `Base.metadata.create_all()` in earlier app runs.

**Solution:** The migration uses `sqlalchemy.inspect()` to check existing columns before adding:

```python
def _existing_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)
    return {col["name"] for col in inspector.get_columns(table_name)}
```

Columns already present are skipped. This makes the migration safe for:
- **Pre-existing DBs missing the columns** — adds them correctly
- **DBs where `create_all()` already added the columns** — skips without error
- **Clean fresh DBs** — all columns added from scratch

### SQLite Compatibility

- Uses `op.batch_alter_table()` throughout (SQLite lacks native `ALTER TABLE ADD COLUMN` with constraints)
- `server_default` string literals used for defaults (`"0.0"`, `"{}"`) — no Python callables
- `render_as_batch=True` already configured in `migrations/env.py`

---

## Migration Run Results

### Test 1: Against production `stockapp.db` (columns already present)

```
INFO  [alembic.runtime.migration] Running upgrade 1ad82d60efcc -> a1b2c3d4e5f6, 
      Add missing columns to trade_journal and analysis_history for pre-existing databases.
```
Result: **SUCCESS** — skipped all 13 columns (already present), advanced version to head.

### Test 2: Against fresh DB with missing columns (`/tmp/test_migration_fresh.db`)

```
INFO  [alembic.runtime.migration] Running upgrade 1ad82d60efcc -> a1b2c3d4e5f6, 
      Add missing columns to trade_journal and analysis_history for pre-existing databases.
```
Result: **SUCCESS** — all 13 columns added. Verified with PRAGMA table_info:

- `trade_journal`: `company_name`, `mood`, `updated_at` — all present
- `analysis_history`: all 10 new columns — all present, zero missing

### Final state of `stockapp.db`

```
a1b2c3d4e5f6 (head)
```

---

## Downgrade

`downgrade()` implemented — removes all 13 columns using the same idempotent pattern (only drops columns that exist). **Not run** (downgrade would destroy data).

---

## Issues Encountered

1. **First run crashed on duplicate column** — `stockapp.db` had columns from `create_all()`. Fixed by adding pre-flight column inspection (idempotent upgrade).

2. **`alembic upgrade head` outputs `ls` listing before migration output** — appears to be a shell hook in the project that runs `ls` before each command. Not a migration issue; all migration output was correct.

---

## Deployment Instructions

For the remote server (`192.168.1.122`):

```bash
ssh saumyapatel@192.168.1.122 "cd /home/saumyapatel/Desktop/nivesh && git pull && cd backend && ../venv/bin/alembic upgrade head"
```

The migration is idempotent — safe to run regardless of the server DB's current column state.
