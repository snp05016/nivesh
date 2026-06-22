# Model Fix Report

Date: 2026-06-16  
File: `backend/models/db_models.py`

---

## FIX-M1: Missing User relationships (HIGH)

### Problem
`User` had no `relationship()` entries for `PortfolioValuationHistory`, `NetWorthLedger`, or `EarningsAlert`. Deleting a User left orphaned rows in all three tables.

### Changes Applied

**User model — added three relationships:**
```python
# Before (end of User relationships block):
device_tokens    = relationship("DeviceToken",     back_populates="user", cascade="all, delete-orphan")

# After:
device_tokens    = relationship("DeviceToken",     back_populates="user", cascade="all, delete-orphan")
portfolio_valuation_history = relationship("PortfolioValuationHistory", back_populates="user", cascade="all, delete-orphan")
net_worth_ledger            = relationship("NetWorthLedger",            back_populates="user", cascade="all, delete-orphan")
earnings_alerts             = relationship("EarningsAlert",             back_populates="user", cascade="all, delete-orphan")
```

**PortfolioValuationHistory — added missing user relationship (none existed):**
```python
# Before: no user relationship
# After (added before __table_args__):
user = relationship("User", back_populates="portfolio_valuation_history")
```

**NetWorthLedger — added back_populates:**
```python
# Before:
user = relationship("User", foreign_keys=[user_id])

# After:
user = relationship("User", foreign_keys=[user_id], back_populates="net_worth_ledger")
```

**EarningsAlert — added back_populates:**
```python
# Before:
user = relationship("User", foreign_keys=[user_id])

# After:
user = relationship("User", foreign_keys=[user_id], back_populates="earnings_alerts")
```

---

## FIX-M2: Missing nullable=False on calibrated_confidence (MEDIUM)

### Problem
`AnalysisHistory.calibrated_confidence` was `Column(Float, default=0.0)` — explicit `None` bypasses the Python-side default and stores NULL, crashing float arithmetic downstream.

### Change Applied
```python
# Before:
calibrated_confidence        = Column(Float, default=0.0)

# After:
calibrated_confidence        = Column(Float, nullable=False, default=0.0, server_default="0.0")
```

`server_default="0.0"` ensures the DB engine also enforces the default, so even raw SQL inserts that omit the column get 0.0 rather than NULL.

---

## FIX-M3: Missing index on AnalysisJob.ticker (MEDIUM)

### Problem
`AnalysisJob.__table_args__` only had an index on `user_id`. Queries filtering by `ticker` (e.g., "is there a running job for RELIANCE?") required a full table scan.

### Change Applied
```python
# Before:
__table_args__ = (
    Index("ix_analysis_jobs_user_id", "user_id"),
)

# After:
__table_args__ = (
    Index("ix_analysis_jobs_user_id", "user_id"),
    Index("ix_analysis_jobs_ticker", "ticker"),
)
```

---

## Verification

```
$ cd backend && python3 -c "from models.db_models import Base, User, PortfolioValuationHistory, NetWorthLedger, EarningsAlert; print('OK')"
OK
```

All three model classes import cleanly with the new relationships and constraints in place.

---

## Next Steps

Run Alembic to generate a migration for FIX-M2 (nullable=False + server_default on calibrated_confidence) and FIX-M3 (new index):

```bash
cd backend
./venv/bin/alembic revision --autogenerate -m "fix calibrated_confidence nullable, add analysis_jobs ticker index"
./venv/bin/alembic upgrade head
./venv/bin/alembic check
```

FIX-M1 (relationships) is ORM-only — no schema migration required.
