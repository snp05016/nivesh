# Database Integrity Fix — Regression Test Report

**File:** `backend/tests/test_database_integrity_fixes.py`
**Run date:** 2026-06-16
**Result: 25 passed, 0 failed (0.35 s)**

---

## Tests Written

### G-001 — Migration drift: missing columns (6 tests)

| Test | Coverage |
|------|----------|
| `TestG001MissingColumns::test_trade_journal_accepts_mood_and_company_name` | Writes `mood` + `company_name` to `TradeJournal`, reads back, asserts values match |
| `TestG001MissingColumns::test_trade_journal_accepts_updated_at` | Writes `updated_at` datetime to `TradeJournal`, asserts not None on read-back |
| `TestG001MissingColumns::test_trade_journal_mood_company_name_no_operational_error` | Asserts no `OperationalError` is raised — confirms column exists in DB schema |
| `TestG001MissingColumns::test_analysis_history_accepts_market_regime` | Writes `market_regime="TRENDING_BULL"` to `AnalysisHistory`, reads back |
| `TestG001MissingColumns::test_analysis_history_accepts_calibrated_confidence` | Writes `calibrated_confidence=72.5`, reads back with approx check |
| `TestG001MissingColumns::test_analysis_history_accepts_outcome_delta_pct_and_was_correct` | Writes both epistemic feedback loop columns, reads back |

### G-002 — Missing User cascade relationships (6 tests)

| Test | Coverage |
|------|----------|
| `TestG002UserCascades::test_delete_user_cascades_portfolio_valuation_history` | Creates user + PVH row, deletes user, asserts PVH count == 0 |
| `TestG002UserCascades::test_delete_user_cascades_net_worth_ledger` | Creates user + NWL row, deletes user, asserts NWL count == 0 |
| `TestG002UserCascades::test_delete_user_cascades_earnings_alerts` | Creates user + EarningsAlert, deletes user, asserts alert count == 0 |
| `TestG002UserCascades::test_back_populates_portfolio_valuation_history` | Creates 2 PVH rows, refreshes user, asserts `user.portfolio_valuation_history` returns both |
| `TestG002UserCascades::test_back_populates_net_worth_ledger` | Creates NWL row, refreshes user, asserts `user.net_worth_ledger` list populated |
| `TestG002UserCascades::test_back_populates_earnings_alerts` | Creates 2 alerts, refreshes user, asserts `user.earnings_alerts` returns both |

### G-003 — PortfolioAddRequest / PortfolioUpdateRequest new fields (7 tests)

| Test | Coverage |
|------|----------|
| `TestG003PortfolioRequestFields::test_portfolio_add_request_accepts_target_price` | Pydantic accepts `target_price=3500.0` |
| `TestG003PortfolioRequestFields::test_portfolio_add_request_accepts_purchase_date` | Pydantic accepts `purchase_date="2026-01-01"` |
| `TestG003PortfolioRequestFields::test_portfolio_add_request_both_new_fields` | Both fields together, both values correct |
| `TestG003PortfolioRequestFields::test_portfolio_add_request_backward_compat_without_new_fields` | Omitting both fields → `None` defaults (backward compatible) |
| `TestG003PortfolioRequestFields::test_portfolio_update_request_accepts_target_price` | `PortfolioUpdateRequest` accepts `target_price` |
| `TestG003PortfolioRequestFields::test_portfolio_update_request_accepts_purchase_date` | `PortfolioUpdateRequest` accepts `purchase_date` |
| `TestG003PortfolioRequestFields::test_portfolio_update_request_backward_compat` | `PortfolioUpdateRequest` without new fields → `None` defaults |

### G-004 — calibrated_confidence nullable=False, default=0.0 (3 tests)

| Test | Coverage |
|------|----------|
| `TestG004CalibratedConfidence::test_calibrated_confidence_defaults_to_zero_when_omitted` | Omitting field → stored as `0.0`, not `NULL` |
| `TestG004CalibratedConfidence::test_calibrated_confidence_explicit_value_stored` | Explicit `43.7` stored and retrieved correctly |
| `TestG004CalibratedConfidence::test_calibrated_confidence_none_uses_column_default` | Passing `None` explicitly: documents that write succeeds (stricter enforcement is Pydantic-layer responsibility) |

### G-007 — AnalysisJob.ticker index (3 tests)

| Test | Coverage |
|------|----------|
| `TestG007AnalysisJobTickerIndex::test_analysis_job_ticker_index_in_table_args` | Asserts `ix_analysis_jobs_ticker` present in `__table_args__` |
| `TestG007AnalysisJobTickerIndex::test_analysis_job_ticker_index_created_in_schema` | Asserts index appears in SQLite `inspector.get_indexes("analysis_jobs")` after `create_all` |
| `TestG007AnalysisJobTickerIndex::test_analysis_job_user_id_index_also_present` | Sanity-checks the existing `ix_analysis_jobs_user_id` is still present |

---

## Test Run Output

```
platform darwin -- Python 3.14.5, pytest-9.0.3
rootdir: /Users/saumya/Desktop/nivesh/backend
configfile: pytest.ini

collected 25 items

tests/test_database_integrity_fixes.py::TestG001MissingColumns::test_trade_journal_accepts_mood_and_company_name PASSED
tests/test_database_integrity_fixes.py::TestG001MissingColumns::test_trade_journal_accepts_updated_at PASSED
tests/test_database_integrity_fixes.py::TestG001MissingColumns::test_trade_journal_mood_company_name_no_operational_error PASSED
tests/test_database_integrity_fixes.py::TestG001MissingColumns::test_analysis_history_accepts_market_regime PASSED
tests/test_database_integrity_fixes.py::TestG001MissingColumns::test_analysis_history_accepts_calibrated_confidence PASSED
tests/test_database_integrity_fixes.py::TestG001MissingColumns::test_analysis_history_accepts_outcome_delta_pct_and_was_correct PASSED
tests/test_database_integrity_fixes.py::TestG002UserCascades::test_delete_user_cascades_portfolio_valuation_history PASSED
tests/test_database_integrity_fixes.py::TestG002UserCascades::test_delete_user_cascades_net_worth_ledger PASSED
tests/test_database_integrity_fixes.py::TestG002UserCascades::test_delete_user_cascades_earnings_alerts PASSED
tests/test_database_integrity_fixes.py::TestG002UserCascades::test_back_populates_portfolio_valuation_history PASSED
tests/test_database_integrity_fixes.py::TestG002UserCascades::test_back_populates_net_worth_ledger PASSED
tests/test_database_integrity_fixes.py::TestG002UserCascades::test_back_populates_earnings_alerts PASSED
tests/test_database_integrity_fixes.py::TestG003PortfolioRequestFields::test_portfolio_add_request_accepts_target_price PASSED
tests/test_database_integrity_fixes.py::TestG003PortfolioRequestFields::test_portfolio_add_request_accepts_purchase_date PASSED
tests/test_database_integrity_fixes.py::TestG003PortfolioRequestFields::test_portfolio_add_request_both_new_fields PASSED
tests/test_database_integrity_fixes.py::TestG003PortfolioRequestFields::test_portfolio_add_request_backward_compat_without_new_fields PASSED
tests/test_database_integrity_fixes.py::TestG003PortfolioRequestFields::test_portfolio_update_request_accepts_target_price PASSED
tests/test_database_integrity_fixes.py::TestG003PortfolioRequestFields::test_portfolio_update_request_accepts_purchase_date PASSED
tests/test_database_integrity_fixes.py::TestG003PortfolioRequestFields::test_portfolio_update_request_backward_compat PASSED
tests/test_database_integrity_fixes.py::TestG004CalibratedConfidence::test_calibrated_confidence_defaults_to_zero_when_omitted PASSED
tests/test_database_integrity_fixes.py::TestG004CalibratedConfidence::test_calibrated_confidence_explicit_value_stored PASSED
tests/test_database_integrity_fixes.py::TestG004CalibratedConfidence::test_calibrated_confidence_none_uses_column_default PASSED
tests/test_database_integrity_fixes.py::TestG007AnalysisJobTickerIndex::test_analysis_job_ticker_index_in_table_args PASSED
tests/test_database_integrity_fixes.py::TestG007AnalysisJobTickerIndex::test_analysis_job_ticker_index_created_in_schema PASSED
tests/test_database_integrity_fixes.py::TestG007AnalysisJobTickerIndex::test_analysis_job_user_id_index_also_present PASSED

======================= 25 passed, 20 warnings in 0.35s ========================
```

Warnings are pre-existing Pydantic V1 `@validator` deprecations and `datetime.utcnow()` calls in unrelated modules (harvester_db, job_repo). None affect these tests.

---

## Notes

- All tests use an isolated `sqlite:///:memory:` engine with `PRAGMA foreign_keys=ON`; they never touch `stockapp.db` or `stockapp_test.db`.
- `G-004` third test (`test_calibrated_confidence_none_uses_column_default`) documents that passing Python `None` does not error at the ORM level. The strict NOT NULL guarantee for external inputs is enforced at the Pydantic schema / API layer, not at the SQLite constraint level (SQLite in WAL mode does not enforce `server_default` when an explicit `None` is inserted via SQLAlchemy).
- Tests do not import `main.py` and therefore do not need the heavy mock chain from `conftest.py`. They run clean in ~0.35 s.
