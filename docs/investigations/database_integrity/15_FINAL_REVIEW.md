# Final Adversarial Review — Database Repair Session
*Griller: Claude Sonnet 4.6 | Date: 2026-06-16*

---

## FIX-M1: User cascade relationships

### Challenge A — Does cascade conflict with `foreign_keys=[user_id]` on child models?

**Evidence found:**

`NetWorthLedger.user`:
```python
user = relationship("User", foreign_keys=[user_id], back_populates="net_worth_ledger")
```

`EarningsAlert.user`:
```python
user = relationship("User", foreign_keys=[user_id], back_populates="earnings_alerts")
```

`PortfolioValuationHistory.user`:
```python
user = relationship("User", back_populates="portfolio_valuation_history")
```

`User` model (parent side):
```python
portfolio_valuation_history = relationship("PortfolioValuationHistory", back_populates="user", cascade="all, delete-orphan")
net_worth_ledger            = relationship("NetWorthLedger",            back_populates="user", cascade="all, delete-orphan")
earnings_alerts             = relationship("EarningsAlert",             back_populates="user", cascade="all, delete-orphan")
```

**Analysis:**

SQLAlchemy requires cascade to be owned on the ONE side of a one-to-many (i.e., `User`), which is what the fix does. The child-side `relationship("User", ...)` definitions are the inverse back-reference — they do NOT carry the cascade. This is the correct pattern.

The `foreign_keys=[user_id]` hint on `NetWorthLedger` and `EarningsAlert` is present because SQLAlchemy requires disambiguation when a model has multiple FK columns (e.g. if a future model has both `user_id` and `approver_id` pointing at `users.id`). Here `NetWorthLedger` has only one FK to `users.id`, so the hint is redundant but harmless.

`PortfolioValuationHistory` does NOT use `foreign_keys=[...]` on its child relationship. The FK is named explicitly in the `Column`:
```python
user_id = Column(Integer, ForeignKey("users.id", name="fk_portfolio_valuation_history_user_id"), ...)
```
Because there is only one FK to `users.id`, SQLAlchemy can resolve the join condition unambiguously. No conflict.

**Verdict: SAFE**

The cascade ownership is correctly on the `User` (parent) side. SQLAlchemy enforces this at mapper configuration time — the test suite `TestG002UserCascades::test_delete_user_cascades_*` would have raised `SAWarning: relationship ... will copy column users.id to column ... which conflicts with mapper` if the cascade direction were wrong. All 6 cascade tests pass.

---

### Challenge B — Was a `user` relationship added to `PortfolioValuationHistory`?

**Evidence found (db_models.py line 298):**
```python
user = relationship("User", back_populates="portfolio_valuation_history")
```

**Verdict: SAFE** — relationship was added correctly in both directions.

---

### Challenge C — Other child models that FK to `users.id` but lack cascade

**Models checked:**

| Model | FK to users.id | User-side cascade | Child back_populates |
|-------|---------------|-------------------|----------------------|
| `Portfolio` | yes | `cascade="all, delete-orphan"` ✓ | `back_populates="portfolio"` ✓ |
| `AnalysisHistory` | yes (nullable) | `cascade="all, delete-orphan"` ✓ | `back_populates="analysis_history"` ✓ |
| `PriceTarget` | yes | `cascade="all, delete-orphan"` ✓ | `back_populates="price_targets"` ✓ |
| `TradeJournal` | yes | `cascade="all, delete-orphan"` ✓ | `back_populates="trade_journal"` ✓ |
| `DeviceToken` | yes | `cascade="all, delete-orphan"` ✓ | `back_populates="device_tokens"` ✓ |
| `PortfolioValuationHistory` | yes | `cascade="all, delete-orphan"` ✓ | `back_populates="user"` ✓ (ADDED by fix) |
| `NetWorthLedger` | yes | `cascade="all, delete-orphan"` ✓ | `back_populates="net_worth_ledger"` ✓ (ADDED by fix) |
| `EarningsAlert` | yes | `cascade="all, delete-orphan"` ✓ | `back_populates="earnings_alerts"` ✓ (ADDED by fix) |
| `AnalysisJob` | yes (nullable) | NO relationship on User | None |
| `SignalEvent` | none | N/A | N/A |

**RISK found: `AnalysisJob`**

`AnalysisJob` has `user_id = Column(Integer, ForeignKey("users.id"), nullable=True)`. There is no `relationship` on `User` for `AnalysisJob` and no cascade. However:
- The column is `nullable=True` — meaning the FK is optional (anonymous jobs are allowed)
- SQLite does NOT enforce FK constraints unless `PRAGMA foreign_keys=ON` is explicitly set per-connection
- The production `database.py` must be checked to confirm whether it enables this pragma

If the production DB enables FK constraints AND a user is deleted, `analysis_jobs` rows with `user_id` pointing at the deleted user will **not** cascade-delete — they will either raise an FK violation error (if FK enforcement is on) or become orphans (if off).

**Verdict: RISK** — `AnalysisJob` rows with `user_id` set are orphaned on user deletion. Not a data corruption risk in SQLite's default mode (FK off), but is an architectural gap. Mitigation: either add a `User.analysis_jobs` relationship with cascade, or set `user_id` to NULL on user deletion via an ON DELETE SET NULL FK constraint.

---

## FIX-M2: `calibrated_confidence` nullable=False

### Challenge A — Does migration `a1b2c3d4e5f6` apply this as nullable=False?

**Evidence found (migration file line 72):**
```python
("calibrated_confidence", sa.Column("calibrated_confidence", Float, nullable=True, server_default="0.0")),
```

**Critical finding:** The migration adds `calibrated_confidence` as **`nullable=True`**, while the ORM model declares it as:
```python
calibrated_confidence = Column(Float, nullable=False, default=0.0, server_default="0.0")
```

**This is a model/migration mismatch.** The column exists in the DB as `nullable=True`. The ORM model says `nullable=False`. In SQLite, this mismatch is **silently ignored** — SQLite does not enforce NOT NULL constraints added after the fact for existing rows, and the column was created as nullable. This means:

1. If the migration runs on a new DB, `calibrated_confidence` is created as `nullable=True`
2. The `nullable=False` in the ORM model is metadata-only and has no enforcement at the DB level in SQLite
3. `NULL` can be stored in this column despite the model declaration

**Additional note:** Running `alembic check` after this migration would likely report a drift because the model says `NOT NULL` but the DB column is `NULLABLE`.

**Verdict: RISK** — The migration column definition contradicts the model. The NOT NULL constraint is not enforced in the actual database. The `test_calibrated_confidence_none_uses_column_default` test in the test report explicitly acknowledges this gap: "passing Python `None` does not error at the ORM level."

The existing test `test_calibrated_confidence_defaults_to_zero_when_omitted` passes because it tests an in-memory DB created via `create_all()`, which DOES honor the model's `nullable=False`. The production DB uses the migration path, which creates the column as nullable.

**Suggested fix:** Either update the migration to use `nullable=False` (requires all existing rows to have non-null values first, or use `server_default="0.0"` plus a data migration), or accept nullable at the DB level and enforce at the Pydantic layer.

---

### Challenge B — Would a NOT NULL migration fail on existing NULL rows?

**Evidence:** The migration currently uses `nullable=True` so this scenario does not arise. If the migration were changed to `nullable=False` and existing rows had NULL values, SQLite's batch mode would fail during the table rebuild unless a `server_default` fills the gap. The existing `server_default="0.0"` would handle this correctly.

**Verdict: SAFE** (not yet a concern given current migration is nullable=True)

---

## FIX-M3: `AnalysisJob.ticker` index

### Challenge A — Is the index in `__table_args__` and reflected in the live DB?

**Evidence found (db_models.py lines 145-148):**
```python
__table_args__ = (
    Index("ix_analysis_jobs_user_id", "user_id"),
    Index("ix_analysis_jobs_ticker", "ticker"),
)
```

**Migration status:** There is NO migration in `migrations/versions/` that adds `ix_analysis_jobs_ticker` to an existing `analysis_jobs` table. The migration `a1b2c3d4e5f6` only touches `trade_journal` and `analysis_history` — it does not touch `analysis_jobs`.

**Impact assessment:** For databases created via `create_all()` (fresh installs), the index exists because SQLAlchemy creates it from `__table_args__`. For databases that were created before this index was added to the model and subsequently migrated (rather than recreated), the index does NOT exist in the DB.

The test `test_analysis_job_ticker_index_created_in_schema` uses `create_all()` in an in-memory DB — it will always pass regardless of whether a migration exists.

**Verdict: RISK** — Production DB may be missing `ix_analysis_jobs_ticker`. No migration adds it to existing databases. An `alembic revision --autogenerate` would catch this drift.

---

## FIX-A1: PortfolioAddRequest / UpdateRequest schema fix

### Challenge A — Can users explicitly CLEAR a target_price via update?

**Evidence found (routers/portfolio.py lines 1022-1025):**
```python
if req.target_price is not None:
    holding.target_price = req.target_price
if req.purchase_date is not None:
    holding.purchase_date = req.purchase_date
```

**Analysis:** The conditional update pattern means `None` is treated as "don't change" rather than "set to NULL". A client that sends `{"target_price": null}` explicitly cannot clear a previously set target price. This is a documented API design limitation.

**Verdict: RISK** — This is a real use-case limitation. If a user sets a target price and later wants to remove it, the API provides no mechanism. The iOS app may work around this by setting `target_price=0.0`, but the ORM model stores 0.0 rather than NULL, which could be misinterpreted downstream as "no target" vs "target is zero". A sentinel value convention or an explicit "clear" endpoint would resolve this cleanly.

**Suggested fix:** Add an explicit `clear_target_price: bool = False` flag, or change the router to use `UNSET` sentinel distinction (Pydantic v2 `model_fields_set`).

---

### Challenge B — Does the update endpoint commit after setting target_price?

**Evidence found (routers/portfolio.py line 1026):**
```python
session.commit()
```

The commit occurs at line 1026, which comes AFTER both conditionals at lines 1022-1025. The sequence is:
1. `holding.shares = req.shares` (line 1020)
2. `holding.buy_price = req.buy_price` (line 1021)
3. `if req.target_price is not None: holding.target_price = req.target_price` (lines 1022-1023)
4. `if req.purchase_date is not None: holding.purchase_date = req.purchase_date` (lines 1024-1025)
5. `session.commit()` (line 1026)

**Verdict: SAFE** — The session is committed correctly after all field updates.

---

## Migration `a1b2c3d4e5f6` Idempotency

### Challenge A — Is `_existing_columns()` implemented correctly?

**Evidence found (migration lines 34-38):**
```python
def _existing_columns(table_name: str) -> set[str]:
    """Return the set of column names currently in *table_name*."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return {col["name"] for col in inspector.get_columns(table_name)}
```

**Analysis:** This uses `sqlalchemy.inspect` on the live connection to query actual DB column metadata. The set comprehension on `col["name"]` is correct. The `not in` check before each `add_column` call is correctly implemented. Running the migration twice will not error — the second run sees the columns already exist and skips them cleanly.

**Verdict: SAFE** — Idempotency is correctly implemented.

---

### Challenge B — Column type mismatch silent pass?

**Evidence:** The idempotency check is `if "column_name" not in existing_columns`. If a column exists with a different type (e.g., `INTEGER` vs `FLOAT`), the check sees the name exists and **skips the add_column entirely**. There is no type validation. This is standard Alembic idempotency behavior — fixing type mismatches requires an explicit `batch_op.alter_column()` in a separate migration.

In the specific case of `calibrated_confidence`: the migration adds it as `Float`. If a previous schema created it as something different, the migration silently passes and the column remains the wrong type.

**Verdict: RISK** (low probability, high consequence if it occurred) — No type verification on skip. Acceptable for this migration's use case since these are all new columns that were never in any prior migration. The realistic risk is near-zero.

---

## Summary Table

| Challenge | Verdict | Severity |
|-----------|---------|----------|
| FIX-M1: Cascade direction correctness | SAFE | — |
| FIX-M1: PortfolioValuationHistory relationship added | SAFE | — |
| FIX-M1: AnalysisJob missing cascade | RISK | LOW |
| FIX-M2: Migration adds calibrated_confidence as nullable=True (model says nullable=False) | RISK | MEDIUM |
| FIX-M2: NOT NULL migration on NULL rows | SAFE | — |
| FIX-M3: ix_analysis_jobs_ticker index missing from migration | RISK | LOW |
| FIX-A1: Cannot explicitly clear target_price via update | RISK | LOW |
| FIX-A1: Session commit after target_price update | SAFE | — |
| Migration idempotency helper correctness | SAFE | — |
| Migration type-mismatch silent pass | RISK | LOW |
