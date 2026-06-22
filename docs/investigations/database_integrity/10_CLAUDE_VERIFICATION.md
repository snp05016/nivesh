# Claude Verification Report — Database Integrity Audit
**Date:** 2026-06-16  
**Auditor:** Claude Sonnet 4.6 (independent re-verification)  
**Files read:**
- `backend/models/db_models.py`
- `backend/migrations/versions/0dc3e605ea33_initial_schema.py`
- `backend/migrations/versions/323c66c5ca0e_auto.py`
- `backend/migrations/versions/1ad82d60efcc_convert_float_to_numeric_for_precision.py`
- `backend/migrations/env.py`
- `backend/database.py`
- `backend/schemas/portfolio.py`

---

## G-001 — Initial Migration Uses `Base.metadata.create_all()` Instead of Granular `op.create_table()` Statements

**Classification:** CONFIRMED  
**Severity:** CRITICAL  
**Fix needed:** YES

### Evidence

`migrations/versions/0dc3e605ea33_initial_schema.py`, lines 21–23:
```python
def upgrade() -> None:
    """Upgrade schema."""
    Base.metadata.create_all(op.get_bind())
```

`migrations/versions/323c66c5ca0e_auto.py`, lines 17–18:
```python
def upgrade() -> None:
    """Base revision already creates the current schema."""
```

`migrations/versions/1ad82d60efcc_convert_float_to_numeric_for_precision.py`, lines 17–18:
```python
def upgrade() -> None:
    """Base revision already creates the current schema."""
```

### Analysis

The initial migration delegates schema creation entirely to `Base.metadata.create_all()`. This approach has a critical flaw: `create_all()` only creates tables that **do not already exist** — it never ALTERs existing tables to add missing columns.

Any database that was initialized before the following columns were added to `db_models.py` will be missing them permanently, because:
1. The initial migration calls `create_all()` once and is then marked as applied.
2. The two subsequent migrations (`323c66c5ca0e` and `1ad82d60efcc`) are both explicit no-ops with no `op.add_column()` statements.

Columns confirmed present in `db_models.py` but NOT guaranteed to exist in pre-existing databases:
- `TradeJournal.company_name` (comment: "added — run migrate_trade_journal.py")
- `TradeJournal.mood` (comment: "added — run migrate_trade_journal.py")
- `TradeJournal.updated_at` (comment: "added — run migrate_trade_journal.py")
- `AnalysisHistory.market_regime` (ML Pipeline — added 2026-06-14)
- `AnalysisHistory.calibrated_confidence` (ML Pipeline — added 2026-06-14)
- `AnalysisHistory.confidence_math_breakdown` (ML Pipeline — added 2026-06-14)
- `AnalysisHistory.conformal_target_upper_3m` (ML Pipeline — added 2026-06-14)
- `AnalysisHistory.conformal_target_lower_3m` (ML Pipeline — added 2026-06-14)
- `AnalysisHistory.quantitative_drivers` (ML Pipeline — added 2026-06-14)
- `AnalysisHistory.tail_risk_flags` (ML Pipeline — added 2026-06-14)

The `TradeJournal` column comments even explicitly reference a workaround script (`migrate_trade_journal.py`), confirming the Alembic migration chain was never updated to carry these columns.

Additionally, newer tables introduced after the initial migration (e.g., `NetWorthLedger`, `MarketAnomaly`, `EarningsSurpriseHistory`, `BlockDeal`, `FIIDIIFlow`, `AdvisorBiography`, `TextAdvisoryInsight`, `IdeasErrorLog`, etc.) are not handled by any migration — they rely entirely on `create_all()` in `init_db()` in `database.py` (line 176), which only runs on fresh databases.

---

## G-002 — `User` Model Missing `back_populates` for `PortfolioValuationHistory`, `NetWorthLedger`, and `EarningsAlert`

**Classification:** CONFIRMED  
**Severity:** HIGH  
**Fix needed:** YES

### Evidence

`models/db_models.py`, lines 29–33 — the `User` model's relationships:
```python
portfolio        = relationship("Portfolio",       back_populates="user", cascade="all, delete-orphan")
analysis_history = relationship("AnalysisHistory", back_populates="user", cascade="all, delete-orphan")
price_targets    = relationship("PriceTarget",     back_populates="user", cascade="all, delete-orphan")
trade_journal    = relationship("TradeJournal",    back_populates="user", cascade="all, delete-orphan")
device_tokens    = relationship("DeviceToken",     back_populates="user", cascade="all, delete-orphan")
```

No relationship to `PortfolioValuationHistory`, `NetWorthLedger`, or `EarningsAlert` is declared on `User`.

Meanwhile, these models reference `users.id` via `ForeignKey` but define their `user` relationship without `back_populates`:

`PortfolioValuationHistory` (lines 280–285): Has `ForeignKey("users.id")` but **no `relationship()` back to `User` at all** (no `user` attribute defined on this model either — the relationship is entirely one-directional via FK only, with no ORM-level link).

`NetWorthLedger` (line 359):
```python
user = relationship("User", foreign_keys=[user_id])
```
No `back_populates` argument. No matching relationship on `User`.

`EarningsAlert` (line 401):
```python
user = relationship("User", foreign_keys=[user_id])
```
No `back_populates` argument. No matching relationship on `User`.

### Impact

- **Cascade delete is broken** for these three tables. Deleting a `User` row will NOT automatically delete orphaned `PortfolioValuationHistory`, `NetWorthLedger`, or `EarningsAlert` rows. This causes referential integrity violations in databases without enforced FK constraints (SQLite without `PRAGMA foreign_keys=ON`, and the FK pragma is only set at the engine `connect` event in `database.py` lines 46–51, which applies at runtime but not during raw SQL tooling).
- SQLAlchemy will emit a warning about relationships lacking `back_populates` counterparts, and bidirectional navigation (`user.net_worth_ledger`) is unavailable.

---

## G-003 — `PortfolioAddRequest` Does Not Support `target_price` and `purchase_date`

**Classification:** CONFIRMED  
**Severity:** MEDIUM  
**Fix needed:** YES

### Evidence

`schemas/portfolio.py`, lines 41–48:
```python
class PortfolioAddRequest(BaseModel):
    user_id: int
    ticker: str
    exchange: str = "NSE"
    company_name: str
    shares: float
    buy_price: float
    group_name: str = "holdings"
```

`models/db_models.py`, lines 49–50:
```python
target_price  = Column(Float, nullable=True)
purchase_date = Column(String, nullable=True)
```

The ORM `Portfolio` model has both `target_price` and `purchase_date` columns (both nullable). The `PortfolioAddRequest` schema exposes neither field to API callers. Any client sending `target_price` or `purchase_date` in a POST body will have those values silently dropped by Pydantic before they reach the router handler.

Note: `PortfolioUpdateRequest` (lines 56–60) also lacks `target_price` and `purchase_date`, meaning these columns can never be set or updated via the API surface — they remain permanently NULL after insertion.

---

## G-004 — `AnalysisHistory.calibrated_confidence` Has `default=0.0` But Lacks `nullable=False`

**Classification:** CONFIRMED  
**Severity:** MEDIUM  
**Fix needed:** YES

### Evidence

`models/db_models.py`, line 91:
```python
calibrated_confidence = Column(Float, default=0.0)
```

The column is defined with a Python-side `default=0.0` but without `nullable=False`. SQLAlchemy column defaults only apply when a row is inserted **without** specifying that column explicitly. If calling code passes `calibrated_confidence=None` explicitly, SQLAlchemy will honor the explicit `None` and insert a SQL NULL — bypassing the default entirely.

### Comparison

Related columns in the same ML Pipeline block:
```python
market_regime               = Column(String, nullable=True)          # correctly nullable=True
calibrated_confidence       = Column(Float, default=0.0)             # MISSING nullable=False
confidence_math_breakdown   = Column(JSON, default="{}")             # also missing nullable=False
quantitative_drivers        = Column(JSON, default=dict)             # also missing nullable=False
tail_risk_flags             = Column(JSON, default=dict)             # also missing nullable=False
```

The semantic intent of `default=0.0` implies the column should never be NULL (a calibrated confidence of zero is meaningful; a NULL is a data quality failure). The missing `nullable=False` constraint means DB-level enforcement is absent.

Additionally, `confidence_math_breakdown`, `quantitative_drivers`, and `tail_risk_flags` share the same pattern: Python-side `default` without `nullable=False`, making them also vulnerable. These were not called out by G-004 but are co-located issues.

---

## G-005 — SQLite WAL Mode and Foreign Keys Not Configured

**Classification:** FALSE_POSITIVE  
**Severity:** N/A  
**Fix needed:** NO

### Evidence

`database.py`, lines 46–51:
```python
@event.listens_for(ENGINE, "connect")
def _set_sqlite_wal(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA synchronous=NORMAL")
    dbapi_conn.execute("PRAGMA busy_timeout=5000")
    dbapi_conn.execute("PRAGMA foreign_keys=ON")
```

Both WAL mode and foreign key enforcement are already configured via SQLAlchemy's `connect` event listener. This fires on every new DBAPI connection, ensuring the PRAGMAs are set for all connections managed by the SQLAlchemy engine (including those created by FastAPI worker threads).

The `check_same_thread=False` flag on the SQLite engine (line 41) combined with the event listener means this configuration is applied correctly across the connection pool.

**Verdict:** The Gemini audit's G-005 finding is a false positive. The code already handles both concerns.

---

## G-006 — `render_as_batch=True` Not Set in `migrations/env.py`

**Classification:** FALSE_POSITIVE  
**Severity:** N/A  
**Fix needed:** NO

### Evidence

`migrations/env.py`, lines 72–77:
```python
context.configure(
    connection=connection,
    target_metadata=target_metadata,
    render_as_batch=True,  # SQLite doesn't support ALTER, use batch mode
)
```

`render_as_batch=True` is already present in `run_migrations_online()`. The comment even explains the rationale. Note, however, that `run_migrations_offline()` (lines 46–54) does NOT include `render_as_batch=True` — but offline mode is rarely used in practice and only affects `alembic upgrade --sql` output generation, not live schema changes.

**Verdict:** False positive for the online migration path (the normal operational path). There is a minor gap in offline mode, but this is LOW severity and non-blocking.

---

## G-007 — `AnalysisJob.ticker` Is Not Indexed

**Classification:** CONFIRMED  
**Severity:** MEDIUM  
**Fix needed:** YES

### Evidence

`models/db_models.py`, lines 119–144 — the full `AnalysisJob` model:
```python
class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    job_id       = Column(String(12), primary_key=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=True)
    ticker       = Column(String(30), nullable=False)          # <-- no index=True
    exchange     = Column(String(10), nullable=False, default="NSE")
    ...
    __table_args__ = (
        Index("ix_analysis_jobs_user_id", "user_id"),
    )
```

The only index on `analysis_jobs` is on `user_id`. The `ticker` column has no index despite being a primary query dimension for job lookups (e.g., "is there an active analysis running for RELIANCE?").

The job repository (`repositories/job_repo.py` — not read but referenced in `database.py` line 326) exposes `get_active_job_for_user_and_type`, which likely filters on both `user_id` AND `ticker`. Without an index on `ticker`, these queries will perform full table scans as the `analysis_jobs` table grows.

A composite index on `(user_id, ticker)` would be more useful than separate indexes, mirroring the pattern used in `Portfolio.__table_args__` (`ix_portfolio_user_ticker`).

---

## G-008 — `AnalysisHistory` Missing Composite Index on `(user_id, ticker)`

**Classification:** FALSE_POSITIVE  
**Severity:** N/A  
**Fix needed:** NO

### Evidence

`models/db_models.py`, lines 100–106:
```python
__table_args__ = (
    Index("ix_analysis_history_user_id", "user_id"),
    Index("ix_analysis_history_ticker", "ticker"),
    Index("ix_analysis_history_scan_type", "scan_type"),
    Index("ix_analysis_history_created_at", "created_at"),
    Index("ix_analysis_history_ticker_user", "ticker", "user_id"),
)
```

A composite index `ix_analysis_history_ticker_user` covering `(ticker, user_id)` already exists at line 105. Note the column order is `(ticker, user_id)` rather than `(user_id, ticker)` — this is suitable for queries filtering by ticker first (e.g., "all analyses for RELIANCE across users") but less optimal for the more common query pattern of "all analyses for a specific user's ticker" which would benefit from `(user_id, ticker)` ordering.

**Verdict:** Partially false positive. A composite index covering both columns exists. The column order `(ticker, user_id)` vs `(user_id, ticker)` matters for query plan optimization in SQLite but is not a missing-index situation. This is at most a MEDIUM-LOW tuning concern, not a missing index.

---

## Summary Table

| Issue | Classification | Severity | Fix Needed |
|-------|---------------|----------|------------|
| G-001: `create_all()` in initial migration; subsequent no-ops; missing columns | CONFIRMED | CRITICAL | YES |
| G-002: `User` missing `back_populates` for 3 models; broken cascade delete | CONFIRMED | HIGH | YES |
| G-003: `PortfolioAddRequest` missing `target_price` and `purchase_date` | CONFIRMED | MEDIUM | YES |
| G-004: `calibrated_confidence` lacks `nullable=False` | CONFIRMED | MEDIUM | YES |
| G-005: SQLite WAL mode / FK pragma not set | FALSE_POSITIVE | N/A | NO |
| G-006: `render_as_batch=True` not in `env.py` | FALSE_POSITIVE | N/A | NO |
| G-007: `AnalysisJob.ticker` not indexed | CONFIRMED | MEDIUM | YES |
| G-008: `AnalysisHistory` missing composite `(user_id, ticker)` index | FALSE_POSITIVE | N/A | NO* |

*A `(ticker, user_id)` composite index exists; column order is suboptimal but the index is present.

---

## Additional Findings (Not in Gemini Audit)

**A-001** — `database.py:init_db()` (line 176) calls `Base.metadata.create_all(ENGINE)` directly. This is a dual-path schema initialization anti-pattern: Alembic migrations and `create_all()` can diverge, causing `alembic check` to show false drift. The AGENTS.md §3.5 explicitly forbids using `create_all()` for schema changes, but `init_db()` still uses it as a seeding entry point.

**A-002** — `confidence_math_breakdown = Column(JSON, default="{}")` uses a string `"{}"` as the default for a `JSON` column. For SQLite this is stored as a string literal; for PostgreSQL this may cause type confusion. The correct default for a JSON column should be `default=dict` (a callable) consistent with `quantitative_drivers` and `tail_risk_flags` on lines 94–95.

**A-003** — `NetWorthLedger` and `EarningsAlert` define `relationship("User", foreign_keys=[user_id])` without `back_populates`. SQLAlchemy will raise `SAWarning: relationship ... will copy column users.id to column net_worth_ledger.user_id` at startup in some versions, and the missing back-reference makes these relationships half-wired.
