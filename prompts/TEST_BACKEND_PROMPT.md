You are a senior backend test architect, database reliability engineer, FastAPI auditor, and adversarial QA agent.

Your task is to perform a long-running, exhaustive backend verification project for this repository.

You must produce two deliverables:

1. A complete backend/database issue report.
2. An exhaustive automated test suite covering the backend from A to Z.
3. Remove the test_api.py file because it is running into an infinite loop and is not useful.

Do not stop at smoke tests. Do not only test happy paths. Do not only test routes. You must test database correctness, API correctness, service correctness, edge cases, failure cases, migrations, concurrency, and financial calculation correctness.

---

# Core Objective

Test literally everything in the backend that can break.

The backend includes:

* FastAPI app
* SQLAlchemy database layer
* ORM models
* Alembic migrations if present
* Routers
* Services
* Portfolio logic
* Market data logic
* Analysis jobs
* Background jobs
* Cache behavior
* LLM-expensive endpoints
* Export endpoints
* Auth
* Watchlist
* Alerts
* Trade journal
* Earnings
* Market dashboard
* Screener
* Stress test
* Copilot
* Harvester
* Options
* Correlation
* Sector rotation

Pay special attention to the existing route structure. Do not assume every route starts with `/api/v1`. Some current routes are unprefixed, including `/login`, `/register`, `/analyze`, `/quick-info`, `/portfolio/{user_id}`, `/market-indices`, `/search`, `/alerts/...`, and `/watchlist/...`.

---

# Agent Loop Structure

Run this as an adversarial multi-agent loop.

## Agent A: Test Builder

Agent A writes tests, proposes coverage, maps code paths, and identifies gaps.

## Agent B: Test Breaker

Agent B attacks Agent A’s tests and asks:

* What code path is still untested?
* What database invariant is missing?
* What edge case is ignored?
* What failure mode is mocked too heavily?
* What route has not been hit?
* What service was tested only through mocks?
* What endpoint has no invalid-input test?
* What transaction behavior is not proven?
* What financial formula could silently be wrong?
* What test would fail on production data?
* What test would catch a migration mismatch?
* What concurrency failure could still happen?

The agents must loop until every backend route, model, service, database table, and critical calculation has either:

1. A real automated test
2. A documented reason it cannot be tested yet
3. A required refactor/testability issue listed in the report

Run at least 4 adversarial loops.

---

# Non-Negotiable Rules

* Do not delete or rewrite production code unless required for testability.
* Prefer adding tests first.
* Do not rely only on mocks.
* Use real test databases wherever possible.
* Use SQLite only if the app actually supports it.
* If production uses Postgres, include Postgres-compatible tests.
* Every database-writing endpoint must have rollback/failure tests.
* Every user-owned resource must have cross-user isolation tests.
* Every financial calculation must have deterministic numeric tests.
* Every API response must be schema-validated.
* Every bug found must have a regression test.
* Every missing constraint must be reported.
* Every route must be accounted for.
* Every test file must be runnable by `pytest`.
* Do not silently skip LLM/network-dependent behavior. Mock external calls, but test the internal contract.
* Do not make fragile tests that depend on live market APIs.
* Do not use real paid LLM APIs in tests.

---

# Phase 1: Backend Inventory

Build a complete backend test inventory.

Map:

* All routers
* All route paths
* HTTP methods
* Request schemas
* Response schemas
* DB models used
* Services called
* External APIs called
* Cache keys used
* Auth requirements
* Expected status codes
* Existing tests
* Missing tests

Create this table:

Route → Router file → Function → DB tables touched → Services touched → Existing tests → Missing tests → Priority

Include known backend areas:

* `backend/main.py`
* `backend/database.py`
* `backend/routers/analysis.py`
* `backend/routers/portfolio.py`
* `backend/routers/market.py`
* `backend/routers/copilot.py`
* `backend/routers/nl_screener.py`
* `backend/routers/stress_test.py`
* `backend/routers/sector_rotation.py`
* `backend/routers/correlation.py`
* `backend/routers/options_strategy.py`
* `backend/services/`
* `backend/tests/`
* Any scripts, seed files, migrations, or background jobs

---

# Phase 2: Database Test Plan

Create tests for every database model and table.

Test:

* Table creation
* Required fields
* Nullable fields
* Defaults
* Primary keys
* Foreign keys
* Unique constraints
* Check constraints
* Cascades
* Relationship loading
* Index assumptions
* Enum/string values
* Timestamp behavior
* Timezone behavior
* Decimal/money precision
* Negative-value rejection where applicable
* Duplicate prevention
* Orphan prevention
* Cross-user ownership isolation

If constraints are missing, write failing tests that prove they are missing, then report the issue.

---

# Phase 3: Migration Tests

If Alembic exists, add tests that verify:

```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
alembic check
```

Also test:

* Empty database migration
* Existing database migration
* ORM schema vs migrated schema
* Destructive migration detection
* Missing downgrade behavior
* Migration order safety

If Alembic does not exist, report that as a high-risk backend issue and create a recommended migration test setup.

---

# Phase 4: API Route Tests

Write exhaustive FastAPI tests using `pytest` and `TestClient` or `httpx.AsyncClient`.

For every route, test:

* Success case
* Missing required parameters
* Invalid parameter types
* Empty inputs
* Boundary values
* Oversized inputs
* Invalid ticker symbols
* Invalid exchange values
* Invalid user IDs
* Unauthorized access if auth applies
* Cross-user access attempts
* Not found behavior
* Duplicate create behavior
* Update missing row behavior
* Delete missing row behavior
* External API failure behavior
* Database failure behavior
* Cache hit behavior
* Cache miss behavior
* Response schema shape
* Status codes
* Error message consistency

Important: Use the current effective paths, not stale planned paths.

Examples of route families to cover:

* Auth: `/login`, `/register`
* Analysis: `/analyze`, `/analyze/active`, `/analyze/job/{job_id}`, `/analyze/batch`
* Quick info: `/quick-info`
* Home feed: `/api/v1/home-feed`
* Technical signals: `/api/v1/technical-signals`
* Portfolio: `/portfolio/{user_id}`, `/portfolio`, `/portfolio/remove`, `/portfolio/update`, `/portfolio/note`
* Portfolio analytics: `/api/v1/portfolio/charts/{user_id}`, `/api/v1/portfolio/valuation-history`, `/portfolio/risk-analysis/{user_id}`, `/portfolio/red-flags/{user_id}`
* Trade journal: `/trade-journal...`
* Market: `/market-indices`, `/search`, `/sector-performance`, `/api/v1/market/stock-history`, `/api/v1/stock-profile`
* Market dashboard: `/api/v1/market/pulse`, `/api/v1/market/momentum`, `/api/v1/market/dashboard`, `/api/v1/market/dashboard-pulse`
* Earnings: `/api/v1/earnings/feed`, `/api/v1/earnings/calendar`, `/api/v1/earnings/estimates`, `/api/v1/earnings/alerts`
* Ideas: `/api/v1/ideas/advisors`, `/api/v1/ideas/feed`
* Alerts: `/alerts/add`, `/alerts/{user_id}`, `/alerts/remove`
* Watchlist: `/watchlist/...`
* Copilot: `/api/v1/copilot/chat`
* Natural language screener: `/api/v1/screener/natural-language`
* Stress test: `/api/v1/portfolio/stress-test`
* Sector rotation: `/api/v1/market/sector-rotation`
* Correlation: `/portfolio/correlation`
* Options payoff: `/api/v1/options/payoff`
* Harvester: `/harvester/feed`, `/harvester/governance/{ticker}`, `/harvester/sources`, `/harvester/search`, `/harvester/stats`

---

# Phase 5: Service Layer Tests

For every service in `backend/services/`, write deterministic tests.

Test:

* Normal inputs
* Empty inputs
* Bad inputs
* Timeout behavior
* External provider failure
* Partial provider failure
* Cache fallback
* Database fallback
* Retry behavior
* Data normalization
* Ticker normalization
* Exchange normalization
* NSE/BSE handling
* Date normalization
* Financial unit normalization
* Error handling
* Logging behavior where important

Do not hit real external APIs in unit tests. Mock external APIs, but assert that internal behavior is correct.

---

# Phase 6: Financial Correctness Tests

Write high-precision tests for all financial logic.

Cover:

* Portfolio total value
* Holdings aggregation
* Average buy price
* Realized P&L
* Unrealized P&L
* Percentage gains
* Allocation percentages
* Valuation history
* Trade journal stats
* Risk analysis inputs
* Stress test inputs
* Stock price history parsing
* Market cap units
* Rupees vs crores vs lakhs
* 0.12 vs 12 percentage bugs
* Negative quantities
* Zero quantity
* Fractional values if supported
* Dividend/split assumptions
* Timezone around Indian market dates

Use `Decimal` expectations where money is involved. Flag any float-based money calculation as a possible issue unless justified.

---

# Phase 7: Transaction and Concurrency Tests

Add tests for:

* Rollback on failed create
* Rollback on failed update
* Rollback on partial service failure
* Duplicate concurrent insert
* Concurrent portfolio updates
* Concurrent watchlist add/remove
* Concurrent analysis job creation
* Session closure
* Commit timing
* Background job collision
* Cache invalidation after commit
* Race condition around unique constraints

If concurrency is hard to test directly, create targeted tests with multiple sessions and document remaining risk.

---

# Phase 8: Contract Tests Against iOS/API Map

Write contract tests that ensure backend routes expected by the iOS app exist and return the expected shapes.

For each Swift-to-backend bridge, test:

* Route exists
* Method is correct
* Required params match
* Basic response shape is stable
* Error response shape is stable

Also test that stale route names are not accidentally used in tests unless intentionally supported.

---

# Phase 9: Fixtures and Test Infrastructure

Create or improve:

* `pytest.ini`
* `conftest.py`
* Test database fixture
* Test client fixture
* Authenticated client fixture
* User factory
* Portfolio factory
* Holding factory
* Watchlist factory
* Alert factory
* Market data factory
* Analysis job factory
* Monkeypatch fixtures for LLM calls
* Monkeypatch fixtures for market APIs
* Cache fake or Redis test fixture
* Time-freezing fixture
* Temporary export directory fixture

Tests must be runnable with:

```bash
pytest -q
```

Also add markers:

```ini
markers =
    unit: fast isolated tests
    integration: database/API integration tests
    contract: API contract tests
    migration: migration tests
    slow: longer-running tests
    concurrency: concurrency/race-condition tests
```

---

# Phase 10: Coverage Enforcement

Add coverage measurement.

Target:

* Minimum backend line coverage: 80%
* Critical database/API path coverage: 95%+
* Every router must have tests
* Every DB model must have tests
* Every financial calculation must have tests

Suggested command:

```bash
pytest --cov=backend --cov-report=term-missing --cov-report=html
```

Do not treat coverage percentage as enough. Coverage must be meaningful.

---

# Phase 11: Adversarial Review Loops

After writing the first test suite, run these loops.

## Loop 1: Route Coverage Attack

List every backend route. Prove each has tests. Add missing tests.

## Loop 2: Database Integrity Attack

List every DB table/model. Prove each has tests. Add missing tests.

## Loop 3: Failure Mode Attack

For every endpoint and service, test what happens when dependencies fail.

## Loop 4: Production Incident Attack

Assume production has:

* Dirty data
* Duplicate rows
* Missing rows
* Slow external APIs
* Partial LLM outage
* Redis outage
* SQLite/Postgres mismatch
* Concurrent requests
* Corrupted cache
* Stale market data
* Invalid tickers
* Timezone edge cases

Add tests or report untestable risks.

---

# Required Final Deliverables

## Deliverable 1: Issue Report

Create:

```text
backend_test_audit_report.md
```

Include:

# Backend Test and Database Audit Report

## Executive Summary

## Test Coverage Inventory

## Confirmed Critical Issues

## Confirmed High-Risk Issues

## Confirmed Medium-Risk Issues

## Confirmed Low-Risk Issues

## Missing Tests Added

## Missing Tests Still Not Possible

## Database Integrity Risks

## API Contract Risks

## Financial Correctness Risks

## Transaction and Concurrency Risks

## Migration Risks

## External Dependency Risks

## Recommended Refactors

## Commands Run

## Commands That Failed

## Final Backend Readiness Score

Score out of 10:

* Route coverage
* Database correctness
* Migration safety
* Financial correctness
* Transaction safety
* API contract stability
* Failure handling
* Test infrastructure
* Production readiness

Every issue must include:

* Severity
* Evidence
* File
* Function
* Reproduction
* Why it matters
* Test added
* Recommended fix

---

## Deliverable 2: Exhaustive Test Suite

Write the actual tests under appropriate files, for example:

```text
backend/tests/
  conftest.py
  test_database_models.py
  test_database_integrity.py
  test_migrations.py
  test_auth_routes.py
  test_analysis_routes.py
  test_portfolio_routes.py
  test_portfolio_financials.py
  test_market_routes.py
  test_earnings_routes.py
  test_alerts_routes.py
  test_watchlist_routes.py
  test_trade_journal_routes.py
  test_copilot_routes.py
  test_screener_routes.py
  test_stress_test_routes.py
  test_sector_rotation_routes.py
  test_correlation_routes.py
  test_options_routes.py
  test_harvester_routes.py
  test_service_layer.py
  test_cache_behavior.py
  test_concurrency.py
  test_api_contract.py
  test_failure_modes.py
```

Also update or add:

```text
pytest.ini
requirements-dev.txt
```

Only add dependencies if needed.

---

# Final Instruction

Begin by inventorying the backend routes, models, services, migrations, and existing tests.

Then write the tests.

Then run the tests.

Then fix only test infrastructure issues needed to make the tests valid.

Then produce the final report.

Do not stop after one pass. Run the adversarial loops until the backend has been grilled from every angle.
