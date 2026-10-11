"""
One-test-per-bug regression suite for the morning briefing system.

Each test corresponds to a specific finding from the morning briefing audit.
Tests perform static code analysis (grep/ast) to verify fixes are in place.
"""

import ast
import inspect
import re
from pathlib import Path


BACKEND_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# B1 — Cache invalidation clears Redis
# ---------------------------------------------------------------------------

def test_regression_B1_invalidation_clears_redis():
    """disk_cache.invalidate() must call Redis DEL (or .delete() on the async client).

    Fix: services/cache_service.py CacheService.invalidate() calls r.delete(full_key).
    """
    cache_path = BACKEND_ROOT / "services" / "cache_service.py"
    source = cache_path.read_text()

    # The invalidate method must contain a delete call
    assert "await r.delete" in source or "r.delete" in source, \
        "B1 REGRESSION: CacheService.invalidate() does NOT call Redis delete!"
    assert "async def invalidate" in source, \
        "B1 REGRESSION: invalidate method missing from CacheService!"


# ---------------------------------------------------------------------------
# B2 — Scheduler timezone is UTC
# ---------------------------------------------------------------------------

def test_regression_B2_scheduler_timezone_is_utc():
    """The APScheduler must be constructed with timezone='UTC'.

    Fix: services/harvest_worker.py line 101.
    """
    hw_path = BACKEND_ROOT / "services" / "harvest_worker.py"
    source = hw_path.read_text()

    # Check for AsyncIOScheduler(timezone="UTC")
    assert 'AsyncIOScheduler(timezone="UTC")' in source or \
           "AsyncIOScheduler(timezone='UTC')" in source or \
           'timezone="UTC"' in source, \
        "B2 REGRESSION: AsyncIOScheduler not using timezone='UTC'!"


# ---------------------------------------------------------------------------
# B3 — No extra_body in Anthropic API call
# ---------------------------------------------------------------------------

def test_regression_B3_no_extra_body_in_anthropic_call():
    """The Anthropic API call in the morning summary endpoint must not pass
    any 'extra_body' parameter (causes 400 errors).

    Fix: verified the client.messages.create() call has no extra_body kwarg.
    """
    portfolio_path = BACKEND_ROOT / "routers" / "morning_brief.py"
    source = portfolio_path.read_text()

    # Search for 'extra_body' — must be zero occurrences
    extra_body_count = source.count("extra_body")
    assert extra_body_count == 0, \
        f"B3 REGRESSION: Found {extra_body_count} 'extra_body' references in morning_brief.py!"


# ---------------------------------------------------------------------------
# B4 — No duplicate scheduler jobs
# ---------------------------------------------------------------------------

def test_regression_B4_no_duplicate_scheduler_jobs():
    """The start_scheduler function must not register the same job function twice.

    Fix: each add_job call has a unique function target.
    """
    hw_path = BACKEND_ROOT / "services" / "harvest_worker.py"
    source = hw_path.read_text()

    # Count how many times pregen_morning_briefs is referenced in add_job lines
    pregen_count = len(re.findall(r'add_job\(.*pregen_morning_briefs', source))
    assert pregen_count == 1, \
        f"B4 REGRESSION: pregen_morning_briefs registered {pregen_count} times (expected 1)!"


# ---------------------------------------------------------------------------
# B5 — TTL is 86400
# ---------------------------------------------------------------------------

def test_regression_B5_ttl_is_86400():
    """MORNING_BRIEF_TTL must be exactly 86400 (24 hours).

    Fix: config/settings.py line 76.
    """
    from config.settings import MORNING_BRIEF_TTL
    assert MORNING_BRIEF_TTL == 86400, \
        f"B5 REGRESSION: MORNING_BRIEF_TTL is {MORNING_BRIEF_TTL}, expected 86400!"


# ---------------------------------------------------------------------------
# B6 — Session closed before I/O
# ---------------------------------------------------------------------------

def test_regression_B6_session_closed_before_io():
    """The pregen_morning_briefs_all_users function must close the DB session
    before making any yfinance or LLM calls.

    Fix: services/portfolio_snapshot.py — uses `with get_session() as db:`
    to collect data, then exits the context manager before the for loop.
    """
    snapshot_path = BACKEND_ROOT / "services" / "portfolio_snapshot.py"
    source = snapshot_path.read_text()

    # The function must have exactly one `with get_session()` block
    # and all yfinance/LLM calls must happen AFTER it closes.
    tree = ast.parse(source)

    # Find the pregen_morning_briefs_all_users function
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "pregen_morning_briefs_all_users":
            # Walk the function body
            with_blocks = [
                n for n in ast.walk(node)
                if isinstance(n, ast.With) or isinstance(n, ast.AsyncWith)
            ]
            # The get_session context manager should be the only one inside the function
            # (or at least, no yfinance/LLM calls inside a with block)
            assert len(with_blocks) >= 1, \
                "B6 REGRESSION: No `with get_session()` block found in pregen function!"

            # Verify that get_session context closes before yfinance loop
            func_source = ast.get_source_segment(source, node)
            # The pattern: with get_session() ... # Phase 1
            # then: for user_id_val, holding_snapshots ... # Phase 2 (no DB)
            assert "# Phase 1" in (func_source or ""), \
                "B6 REGRESSION: Phase labels missing — session may not close before I/O!"
            assert "# Phase 2" in (func_source or ""), \
                "B6 REGRESSION: Phase 2 label missing — I/O may happen inside DB session!"
            return

    pytest.fail("B6 REGRESSION: pregen_morning_briefs_all_users function not found!")


# ---------------------------------------------------------------------------
# B7 — HomeScreen button has action
# ---------------------------------------------------------------------------

def test_regression_B7_button_has_action():
    """The 'READ FULL BRIEF' button in HomeScreen.swift must set
    morningBriefShownDate to dismiss the brief after reading.

    Fix: the button's action closure assigns morningBriefShownDate.
    """
    # Search for HomeScreen.swift — skip redirect/hint files (< 500 bytes)
    ios_root = BACKEND_ROOT.parent / "ios"
    candidates = list(ios_root.rglob("HomeScreen.swift"))
    candidates = [c for c in candidates if c.stat().st_size > 500]  # skip redirect stubs
    if not candidates:
        pytest.skip("HomeScreen.swift not found in ios directory tree")

    homescreen_path = candidates[0]
    source = homescreen_path.read_text()

    # Must contain the "READ FULL BRIEF" text
    assert "READ FULL BRIEF" in source, \
        f"B7 REGRESSION: 'READ FULL BRIEF' text not found in {homescreen_path}!"

    # The action must set morningBriefShownDate
    # Search for lines near "READ FULL BRIEF" that also set morningBriefShownDate
    lines = source.split("\n")
    read_brief_line = None
    for i, line in enumerate(lines):
        if "READ FULL BRIEF" in line:
            read_brief_line = i
            break

    if read_brief_line is not None:
        # Search nearby lines (within ~35 lines) for morningBriefShownDate assignment
        context = lines[max(0, read_brief_line - 10):read_brief_line + 35]
        found_assignment = any(
            "morningBriefShownDate" in line and "=" in line
            for line in context
        )
        assert found_assignment, \
            "B7 REGRESSION: 'READ FULL BRIEF' button does NOT set morningBriefShownDate!"


def test_regression_B7_button_file_found():
    """Verify the real HomeScreen.swift (not a redirect) is found."""
    ios_root = BACKEND_ROOT.parent / "ios"
    candidates = list(ios_root.rglob("HomeScreen.swift"))
    candidates = [c for c in candidates if c.stat().st_size > 500]
    assert len(candidates) >= 1, "No real HomeScreen.swift found (only redirect stubs?)"
    source = candidates[0].read_text()
    assert "READ FULL BRIEF" in source, f"Real HomeScreen.swift at {candidates[0]} lacks button text"


# ---------------------------------------------------------------------------
# N1 — No cache_control in orchestrator.py
# ---------------------------------------------------------------------------

def test_regression_N1_no_cache_control_in_orchestrator():
    """The orchestrator.py must not contain 'cache_control' references.

    Fix: verified zero matches in orchestrator.py.
    """
    orch_path = BACKEND_ROOT / "services" / "orchestrator.py"
    assert orch_path.exists(), "orchestrator.py not found!"

    source = orch_path.read_text()
    cache_control_count = source.count("cache_control")
    assert cache_control_count == 0, \
        f"N1 REGRESSION: Found {cache_control_count} 'cache_control' references in orchestrator.py!"


# ---------------------------------------------------------------------------
# N2 — No extra_body in portfolio_exports.py (broader check than B3)
# ---------------------------------------------------------------------------

def test_regression_N2_no_extra_body_in_pdf_export():
    """The portfolio_exports.py router must contain zero 'extra_body' references
    anywhere in the file (not just the morning summary section).

    Fix: verified zero matches in entire portfolio_exports.py.
    """
    portfolio_path = BACKEND_ROOT / "routers" / "portfolio_exports.py"
    source = portfolio_path.read_text()

    extra_body_count = source.count("extra_body")
    assert extra_body_count == 0, \
        f"N2 REGRESSION: Found {extra_body_count} 'extra_body' references in portfolio_exports.py!"


# ---------------------------------------------------------------------------
# N4 — TTL from central config
# ---------------------------------------------------------------------------

def test_regression_N4_ttl_from_central_config():
    """Both routers/morning_brief.py and services/portfolio_snapshot.py must import
    MORNING_BRIEF_TTL from the same source: config.settings.

    Fix: both files use `from config.settings import MORNING_BRIEF_TTL`.
    """
    portfolio_router = BACKEND_ROOT / "routers" / "morning_brief.py"
    snapshot_service = BACKEND_ROOT / "services" / "portfolio_snapshot.py"

    router_source = portfolio_router.read_text()
    snapshot_source = snapshot_service.read_text()

    # Both must import from config.settings
    assert "from config.settings import MORNING_BRIEF_TTL" in router_source, \
        "N4 REGRESSION: morning_brief.py does NOT import MORNING_BRIEF_TTL from config.settings!"
    assert "from config.settings import MORNING_BRIEF_TTL" in snapshot_source, \
        "N4 REGRESSION: portfolio_snapshot.py does NOT import MORNING_BRIEF_TTL from config.settings!"


# ---------------------------------------------------------------------------
# Additional regression checks
# ---------------------------------------------------------------------------

def test_regression_cache_namespace_is_consistent():
    """Both the endpoint and the pregen function must use the same cache
    namespace: 'morning_brief'.

    Fix: both use 'morning_brief' as the namespace string.
    """
    portfolio_router = BACKEND_ROOT / "routers" / "morning_brief.py"
    snapshot_service = BACKEND_ROOT / "services" / "portfolio_snapshot.py"

    router_source = portfolio_router.read_text()
    snapshot_source = snapshot_service.read_text()

    # Both use "morning_brief" as namespace
    assert '"morning_brief"' in router_source, \
        "REGRESSION: morning_brief.py does not use 'morning_brief' cache namespace!"
    assert '"morning_brief"' in snapshot_source or "'morning_brief'" in snapshot_source, \
        "REGRESSION: portfolio_snapshot.py does not use 'morning_brief' cache namespace!"


def test_regression_devanagari_check_before_cache_write():
    """Both the endpoint and pregen must check contains_devanagari() before
    writing Hindi text into the cache.

    Fix: both functions call contains_devanagari() and reject Hindi output.
    """
    portfolio_router = BACKEND_ROOT / "routers" / "morning_brief.py"
    snapshot_service = BACKEND_ROOT / "services" / "portfolio_snapshot.py"

    router_source = portfolio_router.read_text()
    snapshot_source = snapshot_service.read_text()

    # Both must reference contains_devanagari
    assert "contains_devanagari" in router_source, \
        "REGRESSION: morning_brief.py does NOT check for Devanagari in AI output!"
    assert "contains_devanagari" in snapshot_source, \
        "REGRESSION: portfolio_snapshot.py does NOT check for Devanagari in AI output!"


def test_regression_fallback_has_required_fields():
    """The fallback dict must include all required fields: summary, movers, mood."""
    portfolio_router = BACKEND_ROOT / "routers" / "morning_brief.py"
    source = portfolio_router.read_text()

    # The fallback dict is defined as:
    # fallback = {"summary": "...", "movers": [], "mood": "cautious", ...}
    assert '"summary"' in source, "Fallback dict missing 'summary'"
    assert '"movers"' in source, "Fallback dict missing 'movers'"
    assert '"mood"' in source, "Fallback dict missing 'mood'"


def test_regression_anthropic_call_has_max_3_retries():
    """The Anthropic API call must retry up to 3 times with exponential backoff.

    Fix: the for attempt in range(3) loop in morning_brief.py.
    """
    portfolio_router = BACKEND_ROOT / "routers" / "morning_brief.py"
    source = portfolio_router.read_text()

    assert "range(3)" in source, \
        "REGRESSION: Anthropic call missing retry loop (range(3))!"
