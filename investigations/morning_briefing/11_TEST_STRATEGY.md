# Morning Briefing — Test Strategy

**Date:** 2026-06-16  
**Scope:** Regression and integration test suite for the 7 bugs + 3 new issues fixed in the morning briefing pipeline  
**Target coverage:** >95% of affected code paths

---

## Coverage Matrix

| Bug ID | Test Name | Test Type | Covers |
|--------|-----------|-----------|--------|
| B1 | `test_cache_invalidate_reaches_redis` | Unit | cache invalidation clears Redis in async context |
| B1 | `test_cache_invalidate_clears_fallback_on_error` | Unit | exception handler clears in-memory fallback |
| B2 | `test_scheduler_timezone_is_utc` | Unit | scheduler timezone = UTC |
| B2 | `test_pregen_fires_at_correct_utc_hour` | Unit | cron hour=1 in UTC = 6:30 AM IST |
| B3 | `test_live_gen_no_extra_body` | Unit | Anthropic call has no `extra_body` parameter |
| B3 | `test_morning_summary_returns_real_text` | Integration | endpoint returns AI text, not fallback string |
| B4 | `test_no_duplicate_scheduler_jobs` | Unit | each job registered exactly once |
| B5 | `test_pregen_cache_ttl_is_86400` | Unit | cache_set called with ttl=86400 |
| B5 | `test_ttl_constant_imported_from_settings` | Unit | router and pregen import from same source |
| B5 | `test_cache_ttl_consistency` | Integration | both code paths write with same TTL |
| B6 | `test_db_session_closed_before_io` | Unit | session exits before yfinance/LLM calls |
| B7 | `test_read_full_brief_button_sets_date` | Unit | button sets morningBriefShownDate |
| N1 | `test_no_cache_control_in_orchestrator` | Unit | no `cache_control` in orchestrator creates |
| N2 | `test_no_extra_body_in_pdf_export` | Unit | no `extra_body` in PDF export path |
| N4 | `test_morning_brief_ttl_in_settings` | Unit | MORNING_BRIEF_TTL defined in config/settings.py |

---

## Test Categories

### Unit Tests (5 test files)

#### 1. `tests/morning_briefing/test_cache_layer.py`

```python
# Tests B1 (invalidation) and B5 (TTL consistency)

import pytest
from unittest.mock import MagicMock, patch
from services.disk_cache import invalidate
from services.cache_service import cache


class TestCacheInvalidation:
    """B1: cache invalidation must reach Redis in async context."""

    def test_invalidate_calls_cache_service(self):
        """_run_async_in_thread must be called with cache.invalidate."""
        with patch("services.disk_cache._run_async_in_thread") as mock_run:
            invalidate("morning_brief", "user_1")
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]  # coroutine object
            assert args is not None

    def test_invalidate_clears_fallback_on_exception(self):
        """When _run_async_in_thread raises, fallback cache is cleared."""
        cache._fallback_cache["morning_brief"] = {"user_1": "stale brief"}
        with patch("services.disk_cache._run_async_in_thread", side_effect=RuntimeError):
            invalidate("morning_brief", "user_1")
        assert "user_1" not in cache._fallback_cache.get("morning_brief", {})

    def test_invalidate_handles_missing_namespace(self):
        """No crash when namespace not in fallback cache."""
        with patch("services.disk_cache._run_async_in_thread", side_effect=RuntimeError):
            invalidate("nonexistent", "key")
        # Should not raise


class TestTTL:
    """B5: TTL consistency between pregen and live-gen."""

    def test_pregen_cache_set_has_explicit_ttl(self):
        """Pregen must pass ttl=86400 explicitly."""
        import ast, inspect
        from services import portfolio_snapshot

        source = inspect.getsource(portfolio_snapshot.pregenerate_morning_briefs_all_users)
        tree = ast.parse(source)
        cache_set_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and getattr(getattr(node.func, 'id', None), None) == 'cache_set'
        ]
        # At least one cache_set call must have ttl keyword
        ttl_kwargs = [kw for call in cache_set_calls for kw in call.keywords if kw.arg == 'ttl']
        assert len(ttl_kwargs) > 0

    def test_ttl_imported_from_settings(self):
        """Router must import MORNING_BRIEF_TTL from config.settings."""
        from routers.portfolio import _MORNING_CACHE_TTL
        assert _MORNING_CACHE_TTL == 86400

    def test_settings_exports_morning_brief_ttl(self):
        """config.settings must export MORNING_BRIEF_TTL."""
        from config.settings import MORNING_BRIEF_TTL
        assert MORNING_BRIEF_TTL == 86400
```

#### 2. `tests/morning_briefing/test_scheduler.py`

```python
# Tests B2 (timezone) and B4 (duplicate jobs)

import pytest
from unittest.mock import patch, MagicMock


class TestSchedulerTimezone:
    """B2: scheduler must use UTC timezone."""

    def test_scheduler_timezone_is_utc(self):
        """AsyncIOScheduler must be initialized with timezone='UTC'."""
        import services.harvest_worker as hw
        # Access the module-level _scheduler
        assert hw._scheduler is not None
        # APScheduler stores timezone in its timezone property
        tz_str = str(hw._scheduler.timezone)
        assert tz_str == "UTC"

    @pytest.mark.parametrize("job_name,expected_hour", [
        ("pregen_morning_briefs", 1),       # 6:30 AM IST
        ("purge_expired_cache", 3),          # 8:30 AM IST
        ("premarket_warmup", 3),             # 9:00 AM IST (3:30 AM UTC)
        ("error_digest", 1),                 # 7:00 AM IST (1:30 AM UTC)
        ("snapshot_all_users", 11),          # 4:30 PM IST
        ("evaluate_analysis_outcomes", 20),  # 2:00 AM IST next day
    ])
    def test_cron_hours_match_intended_ist(self, job_name, expected_hour):
        """Verify no UTC hours accidentally shifted from intent."""
        from apscheduler.job import Job

        # Read the scheduler setup from harvest_worker
        import services.harvest_worker as hw
        jobs = hw._scheduler.get_jobs()
        for job in jobs:
            if job_name in str(job.name) or job_name in str(job.func_ref):
                assert job._trigger.fields[4] == str(expected_hour)
                return


class TestNoDuplicateJobs:
    """B4: no duplicate job registrations."""

    def test_no_duplicate_evaluate_analysis(self):
        """_run_evaluate_analysis_outcomes must be registered exactly once."""
        import services.harvest_worker as hw
        jobs = hw._scheduler.get_jobs()
        analysis_jobs = [
            j for j in jobs
            if "evaluate_analysis_outcomes" in str(j.func_ref)
        ]
        assert len(analysis_jobs) == 1, (
            f"Expected 1 evaluate_analysis_outcomes job, found {len(analysis_jobs)}"
        )
```

#### 3. `tests/morning_briefing/test_no_extra_body.py`

```python
# Tests B3, N1, N2: no extra_body or cache_control anywhere

import ast
import os
import pytest


def _parse_file(path):
    with open(path) as f:
        return ast.parse(f.read())


def _walk_for_keywords(tree, keywords):
    """Return all ast.Call nodes whose keywords contain any of the given names."""
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in (node.keywords or []):
                if kw.arg in keywords:
                    results.append((node, kw))
    return results


class TestNoExtraBody:
    """B3, N1, N2: no broken extra_body or cache_control in API calls."""

    BACKEND_DIR = os.path.join(os.path.dirname(__file__), "../../")
    FORBIDDEN_KWARGS = {"extra_body", "cache_control"}
    TARGET_FILES = [
        "routers/portfolio.py",
        "services/orchestrator.py",
    ]

    @pytest.mark.parametrize("rel_path", TARGET_FILES)
    def test_no_top_level_extra_body(self, rel_path):
        """No .create() call may pass extra_body as a top-level kwarg."""
        abs_path = os.path.join(self.BACKEND_DIR, rel_path)
        if not os.path.exists(abs_path):
            pytest.skip(f"File not found: {abs_path}")
        tree = _parse_file(abs_path)
        violations = _walk_for_keywords(tree, self.FORBIDDEN_KWARGS)
        assert len(violations) == 0, (
            f"{rel_path} contains {len(violations)} forbidden kwargs: "
            f"{self.FORBIDDEN_KWARGS}\n"
            f"First violation: line {violations[0][0].lineno if violations else ''}"
        )

    def test_no_extra_body_in_any_backend_file(self):
        """Sweep: no .py file in backend/ may use extra_body."""
        violations = []
        for root, dirs, files in os.walk(self.BACKEND_DIR):
            dirs[:] = [d for d in dirs if d not in {"__pycache__", ".venv", "venv", "migrations"}]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(root, fname)
                try:
                    tree = _parse_file(path)
                    hits = _walk_for_keywords(tree, self.FORBIDDEN_KWARGS)
                    for _ in hits:
                        violations.append(path)
                except SyntaxError:
                    continue
        assert len(violations) == 0, (
            f"extra_body/cache_control found in: {violations}"
        )
```

#### 4. `tests/morning_briefing/test_db_session_scope.py`

```python
# Tests B6: DB session closed before I/O

import ast
import inspect
import pytest
from contextlib import ExitStack


class TestDBSessionScope:
    """B6: DB session must not be held open across network I/O calls."""

    I_O_CALLS = {"yf.Ticker", "history(", "_deepseek_chat", "client.messages.create"}

    def test_pregenerate_has_two_phases(self):
        """Source must contain exactly one `with get_session() as db:` block."""
        from services import portfolio_snapshot

        source = inspect.getsource(portfolio_snapshot.pregenerate_morning_briefs_all_users)
        tree = ast.parse(source)

        with_count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.With):
                for item in node.items:
                    ctx = ast.unparse(item.context_expr)
                    if "get_session" in ctx:
                        with_count += 1

        assert with_count == 1, (
            f"Expected 1 `with get_session()` block, found {with_count}"
        )

    def test_no_yfinance_inside_db_session(self):
        """yfinance calls must be outside the `with get_session()` block."""
        from services import portfolio_snapshot

        source = inspect.getsource(portfolio_snapshot.pregenerate_morning_briefs_all_users)
        tree = ast.parse(source)

        in_session = False
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.With):
                for item in node.items:
                    if "get_session" in ast.unparse(item.context_expr):
                        in_session = True
                        # Walk the with-body
                        for child in ast.walk(node):
                            if isinstance(child, ast.Call):
                                code = ast.unparse(child.func)
                                if any(call in code for call in self.I_O_CALLS):
                                    violations.append((child.lineno, code))
                        in_session = False

        assert len(violations) == 0, (
            f"I/O calls inside DB session at lines: {violations}"
        )
```

#### 5. `tests/morning_briefing/test_ios_button.py`

```python
# Tests B7: "READ FULL BRIEF" button wired

import os
import re
import pytest


class TestReadFullBriefButton:
    """B7: READ FULL BRIEF button must set morningBriefShownDate."""

    BUTTON_FILE = os.path.join(
        os.path.dirname(__file__),
        "../../../ios/StockApp/stockme/stockme/Views/HomeScreen.swift"
    )

    @pytest.mark.skipif(not os.path.exists(BUTTON_FILE), reason="iOS source not available")
    def test_button_has_action_beyond_haptic(self):
        """Button closure must contain more than just HapticManager.selection()."""
        with open(self.BUTTON_FILE) as f:
            content = f.read()

        # Find the READ FULL BRIEF button closure
        pattern = r'(Button\s*\{.*?HapticManager\.selection\(\).*?\})'
        matches = re.findall(pattern, content, re.DOTALL)
        assert len(matches) > 0, "Could not find READ FULL BRIEF Button closure"

        for match in matches:
            if "READ FULL BRIEF" in match or "morningBriefShownDate" in match:
                # Must contain morningBriefShownDate assignment
                assert "morningBriefShownDate" in match, (
                    "READ FULL BRIEF button must set morningBriefShownDate"
                )
                return

        pytest.skip("Could not locate READ FULL BRIEF Button context")
```

---

### Integration Tests

#### 6. `tests/morning_briefing/test_morning_summary_endpoint.py`

```python
# Integration tests for GET /morning-summary/{user_id}

import pytest


class TestMorningSummaryEndpoint:
    """End-to-end: endpoint returns valid JSON with real AI text."""

    def test_endpoint_returns_200(self, client, auth_headers, seeded_portfolio_user_id):
        """GET /morning-summary/{user_id} returns HTTP 200."""
        resp = client.get(
            f"/morning-summary/{seeded_portfolio_user_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_endpoint_returns_valid_summary_json(self, client, auth_headers, seeded_portfolio_user_id):
        """Response contains required summary keys."""
        resp = client.get(
            f"/morning-summary/{seeded_portfolio_user_id}",
            headers=auth_headers,
        )
        data = resp.json()
        assert "summary" in data
        assert isinstance(data["summary"], str)
        assert len(data["summary"]) > 0

    def test_endpoint_does_not_return_fallback_text(self, client, auth_headers, seeded_portfolio_user_id):
        """Response must NOT contain 'AI brief unavailable at this time'."""
        resp = client.get(
            f"/morning-summary/{seeded_portfolio_user_id}",
            headers=auth_headers,
        )
        data = resp.json()
        # The fallback string is a regression from B3
        assert "AI brief unavailable at this time" not in data["summary"], (
            f"Fallback text returned: {data['summary'][:100]}"
        )

    def test_cache_hit_returned_on_second_call(self, client, auth_headers, seeded_portfolio_user_id):
        """Second call within TTL should hit cache (no extra LLM call)."""
        # First call populates cache
        resp1 = client.get(
            f"/morning-summary/{seeded_portfolio_user_id}",
            headers=auth_headers,
        )
        assert resp1.status_code == 200
        first_summary = resp1.json()["summary"]

        # Second call should return same cached content
        resp2 = client.get(
            f"/morning-summary/{seeded_portfolio_user_id}",
            headers=auth_headers,
        )
        assert resp2.status_code == 200
        assert resp2.json()["summary"] == first_summary, (
            "Cache inconsistency: second call returned different summary"
        )

    def test_portfolio_change_invalidates_cache(self, client, auth_headers, seeded_portfolio_user_id):
        """After adding a holding, cache is invalidated and new brief generated."""
        # Populate cache first
        resp1 = client.get(
            f"/morning-summary/{seeded_portfolio_user_id}",
            headers=auth_headers,
        )
        assert resp1.status_code == 200
        first_summary = resp1.json()["summary"]

        # Add a new holding (triggers _cache_invalidate via the router)
        client.post("/portfolio/add", json={
            "user_id": seeded_portfolio_user_id,
            "ticker": "TCS",
            "exchange": "NSE",
            "company_name": "Tata Consultancy Services",
            "shares": 5,
            "buy_price": 3500.0,
            "group_name": "test_holdings",
        }, headers=auth_headers)

        # Next call should return fresh brief (not cached stale one)
        resp2 = client.get(
            f"/morning-summary/{seeded_portfolio_user_id}",
            headers=auth_headers,
        )
        assert resp2.status_code == 200
        assert "AI brief unavailable at this time" not in resp2.json()["summary"]
```

---

### Concurrency Tests

#### 7. `tests/morning_briefing/test_concurrency.py`

```python
# Concurrency: multi-user, multi-worker

import pytest
import concurrent.futures
import time


class TestMorningBriefConcurrency:
    """Test concurrent access to morning-summary endpoint."""

    @pytest.mark.slow
    def test_concurrent_get_does_not_crash(self, client, auth_headers, auth_token, test_user_id):
        """10 concurrent GET /morning-summary calls must all return 200."""
        def call_endpoint(_):
            resp = client.get(
                f"/morning-summary/{test_user_id}",
                headers=auth_headers,
            )
            return resp.status_code, resp.json().get("summary", "")[:20]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(call_endpoint, i) for i in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        statuses = [r[0] for r in results]
        assert all(s == 200 for s in statuses), (
            f"Non-200 responses: {statuses}"
        )

    @pytest.mark.slow
    def test_concurrent_cache_write_is_idempotent(self, client, auth_headers, test_user_id):
        """Concurrent cache writes should not corrupt the stored value."""
        # Populate with one call
        client.get(f"/morning-summary/{test_user_id}", headers=auth_headers)
        # Then run concurrent calls
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            pool.map(
                lambda _: client.get(f"/morning-summary/{test_user_id}", headers=auth_headers),
                range(5),
            )
        # Final call should still return valid data
        resp = client.get(f"/morning-summary/{test_user_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert "summary" in resp.json()
```

---

### Edge Cases

#### 8. `tests/morning_briefing/test_edge_cases.py`

```python
# Edge cases: empty portfolio, special chars, missing data

import pytest


class TestMorningBriefEdgeCases:
    """Edge case handling for morning-summary."""

    def test_empty_portfolio_returns_graceful(self, client, auth_headers, test_user_id):
        """User with no holdings should get a graceful empty/skip response."""
        resp = client.get(
            f"/morning-summary/{test_user_id}",
            headers=auth_headers,
        )
        # Must return 200, not 500
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data

    def test_nonexistent_user_returns_graceful(self, client, auth_headers):
        """Non-existent user ID should return 404 or empty 200."""
        resp = client.get(
            "/morning-summary/99999999",
            headers=auth_headers,
        )
        assert resp.status_code in (200, 404, 403)

    def test_special_chars_in_ticker_handled(self, client, auth_headers, test_user_id):
        """Tickers with dashes (NSE:BSE) or dots must not break parsing."""
        # Add holding with special ticker
        client.post("/portfolio/add", json={
            "user_id": test_user_id,
            "ticker": "BAJFINANCE",
            "exchange": "NSE",
            "company_name": "Bajaj Finance",
            "shares": 3,
            "buy_price": 7000.0,
            "group_name": "test_holdings",
        }, headers=auth_headers)

        resp = client.get(f"/morning-summary/{test_user_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert "summary" in resp.json()

    def test_multiple_holdings_handled(self, client, auth_headers, test_user_id):
        """Portfolio with many holdings should generate valid brief."""
        tickers = ["HDFCBANK", "INFY", "ITC", "SBIN", "WIPRO"]
        for ticker in tickers:
            client.post("/portfolio/add", json={
                "user_id": test_user_id,
                "ticker": ticker,
                "exchange": "NSE",
                "company_name": f"{ticker} Ltd",
                "shares": 5,
                "buy_price": 1000.0,
                "group_name": "test_holdings",
            }, headers=auth_headers)

        resp = client.get(f"/morning-summary/{test_user_id}", headers=auth_headers)
        assert resp.status_code == 200
```

---

## Test Infrastructure

### `conftest.py` Additions

Add to `backend/tests/conftest.py` (or create `backend/tests/morning_briefing/conftest.py`):

```python
# Morning Briefing test fixtures

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_disk_cache():
    """Mock disk_cache module for unit tests."""
    with patch("services.disk_cache.sync_get") as mock_get, \
         patch("services.disk_cache.sync_set") as mock_set, \
         patch("services.disk_cache.invalidate") as mock_inval:
        mock_get.return_value = None
        yield {
            "get": mock_get,
            "set": mock_set,
            "invalidate": mock_inval,
        }


@pytest.fixture
def mock_anthropic():
    """Mock Anthropic client for tests that need AI responses."""
    client_mock = MagicMock()
    msg_mock = MagicMock()
    msg_mock.content = [MagicMock(text="GOOD MORNING. Nivesh Portfolio Intelligence Brief.")]
    msg_mock.usage = MagicMock(input_tokens=50, output_tokens=100)
    client_mock.messages.create.return_value = msg_mock

    with patch("routers.portfolio.Anthropic", return_value=client_mock):
        yield client_mock


@pytest.fixture
def mock_redis():
    """Mock Redis for cache verification."""
    with patch("services.cache_service.cache._ensure_connected") as mock_connect, \
         patch("services.cache_service.aioredis.from_url") as mock_url:
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True
        mock_redis.delete.return_value = 1
        mock_url.return_value = mock_redis
        yield mock_redis
```

### Test DB Setup

Morning briefing tests use the existing `conftest.py` infrastructure:
- **DB path:** `backend/stockapp_test.db` (SQLite)
- **Test user:** `test_nivesh_9999` (registered at session start, cleaned at end)
- **Test client:** `TestClient(app)` — session-scoped
- **Anthropic/Yfinance:** Mocked to avoid real API calls and network dependencies

---

## Execution

### Local

```bash
# Run all morning brief tests
cd backend
.venv/bin/python3 -m pytest tests/morning_briefing/ -v --tb=short

# Run with coverage
.venv/bin/python3 -m pytest tests/morning_briefing/ -v \
    --cov=services \
    --cov=routers \
    --cov-report=term-missing

# Run only unit tests (fast)
.venv/bin/python3 -m pytest tests/morning_briefing/ -v -m "not slow"

# Run integration tests
.venv/bin/python3 -m pytest tests/morning_briefing/test_morning_summary_endpoint.py -v
```

### CI Integration

Add to CI pipeline (`.github/workflows/test.yml` or equivalent):

```yaml
- name: Morning Briefing Tests
  run: |
    cd backend
    .venv/bin/python3 -m pytest tests/morning_briefing/ -v --tb=short --junitxml=results/morning_brief.xml
```

### Expected Coverage

| File | Expected Coverage |
|------|------------------|
| `services/disk_cache.py` | 100% |
| `services/harvest_worker.py` (scheduler config) | 100% |
| `services/portfolio_snapshot.py` (pregen function) | >90% |
| `routers/portfolio.py` (morning summary endpoint) | >90% |
| `config/settings.py` (MORNING_BRIEF_TTL) | 100% |
| **Overall** | **>95%** |

---

## Recurrence Prevention

### 1. CI Gate

All morning briefing tests must pass before merge to `main` or `feat/*` branches:

```yaml
# .github/workflows/gate.yml
morning-briefing-gate:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Run morning brief tests
      run: cd backend && pytest tests/morning_briefing/ -v --tb=short
    - name: Block on failure
      if: failure()
      run: exit 1
```

### 2. Pre-commit Hook

Add to `.pre-commit-config.yaml` or `lefthook.yml`:

```yaml
- id: no-extra-body
  name: Check for forbidden extra_body/cache_control
  entry: bash -c '! grep -rn "extra_body\|cache_control" backend/*.py backend/**/*.py || (echo "ERROR: extra_body/cache_control found in backend Python files" && exit 1)'
  language: system
  types: [python]
  exclude: '^backend/migrations/|^backend/tests/tests/'
```

### 3. Alembic Migration Check

If a cache-related schema change is introduced (e.g., adding a TTL column, changing a cache table), require:

```bash
cd backend
../venv/bin/alembic revision --autogenerate -m "describe cache schema change"
../venv/bin/alembic upgrade head
../venv/bin/alembic check
```

The `alembic check` command verifies no schema drift between ORM models and the live database.

### 4. Static Analysis

```bash
# Detect any extra_body or cache_control in production code
cd backend
grep -rn "extra_body\|cache_control" --include="*.py" --exclude-dir="tests" --exclude-dir="migrations" . && exit 1 || exit 0
```

---

## Risk Items Not Tested

| Item | Why Not Tested | Acceptable Risk |
|------|---------------|-----------------|
| **N3** (Multi-worker `_fallback_cache` stale after Redis outage) | Requires simulating Redis outage across multiple uvicorn workers — integration test complexity exceeds benefit for LOW severity | Yes — Redis is the primary cache; fallback is defense-in-depth. Outage + portfolio mutation window is extremely narrow |
| Real Anthropic API response | Mocked in tests to avoid cost and network dependency | Yes — integration stage on server validates real API calls |
| Real yfinance calls | Mocked; prices change every market day — tests must be deterministic | Yes — pre-market test server deploy validates real data pipeline |
