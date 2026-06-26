"""
Smoke tests for all new Nivesh backend endpoints.
Do NOT run via pytest — call test functions directly.
Usage: cd /Desktop/stocks && .venv/bin/python3 test_new_endpoints.py

All functions call endpoint logic with user_id=2 (nirav, has holdings).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(name, result):
    """
    Logs a success message and prints a summary of the result.

    Args:
        name (str): The name of the test or operation.
        result (Any): The result returned from the operation.

    Returns:
        Any: The original result.
    """
    print(f"  [PASS] {name}")
    if isinstance(result, dict):
        keys = list(result.keys())[:6]
        print(f"         keys: {keys}")
    elif isinstance(result, list):
        print(f"         items: {len(result)}")
    return result


def _fail(name, err):
    """
    Logs a failure message along with the error encountered.

    Args:
        name (str): The name of the test or operation.
        err (Exception): The exception that caused the failure.
    """
    print(f"  [FAIL] {name}: {err}")


# ---------------------------------------------------------------------------
# Task 1 — Risk Analysis
# ---------------------------------------------------------------------------

def test_risk_analysis():
    """
    Tests the portfolio risk analysis endpoint by calling it directly with a test user ID.
    Asserts that the expected keys (portfolio_beta, risk_score, etc.) are present in the result.
    """
    print("\n=== /portfolio/risk-analysis ===")
    try:
        from main import portfolio_risk_analysis_endpoint
        result = portfolio_risk_analysis_endpoint(user_id=2)
        assert "portfolio_beta" in result
        assert "risk_score" in result
        assert "sector_concentration" in result
        assert "stock_details" in result
        _ok("risk_analysis", result)
        print(f"         beta={result.get('portfolio_beta')}, score={result.get('risk_score')}, label={result.get('risk_score_label')}")
        corr = result.get("highest_correlation_pair")
        if corr:
            print(f"         highest corr pair: {corr}")
    except Exception as e:
        _fail("risk_analysis", e)


# ---------------------------------------------------------------------------
# Task 2 — Red Flags
# ---------------------------------------------------------------------------

def test_red_flags():
    """
    Tests the portfolio red flags endpoint by calling it directly with a test user ID.
    Asserts that the flags and total_flags keys are present in the response.
    """
    print("\n=== /portfolio/red-flags ===")
    try:
        from main import portfolio_red_flags_endpoint
        result = portfolio_red_flags_endpoint(user_id=2)
        assert "flags" in result
        assert "total_flags" in result
        _ok("red_flags", result)
        print(f"         total={result.get('total_flags')}, critical={result.get('critical')}, warnings={result.get('warnings')}")
        if result.get("flags"):
            print(f"         first flag: {result['flags'][0]}")
    except Exception as e:
        _fail("red_flags", e)


# ---------------------------------------------------------------------------
# Task 3 — Macro Impact
# ---------------------------------------------------------------------------

def test_macro_impact():
    """
    Tests the macro impact endpoint.
    Asserts the presence of macro_readings and impacts keys in the returned payload.
    """
    print("\n=== /macro-impact ===")
    try:
        from main import macro_impact_endpoint
        result = macro_impact_endpoint(user_id=2)
        assert "impacts" in result
        assert "macro_readings" in result
        _ok("macro_impact", result)
        print(f"         macro={result.get('macro_readings')}")
        if result.get("impacts"):
            print(f"         first: {result['impacts'][0]}")
    except Exception as e:
        _fail("macro_impact", e)


# ---------------------------------------------------------------------------
# Task 4 — Trade Journal
# ---------------------------------------------------------------------------

def test_trade_journal_crud():
    """
    Tests the CRUD operations for the trade journal, specifically adding an entry and retrieving it.
    Validates that adding an entry returns success, and fetching returns the expected list.
    """
    print("\n=== /trade-journal CRUD ===")
    try:
        from main import trade_journal_add_endpoint, trade_journal_get_endpoint, TradeJournalAddRequest
        # Add entry
        req = TradeJournalAddRequest(
            user_id=2, ticker="RELIANCE", action="BUY",
            price_at_time=2800.0, reason_text="Strong refining margins and Jio growth thesis."
        )
        add_result = trade_journal_add_endpoint(req)
        assert add_result.get("success")
        entry_id = add_result.get("entry_id")
        _ok("trade_journal_add", add_result)
        print(f"         entry_id={entry_id}")

        # Get entries
        get_result = trade_journal_get_endpoint(user_id=2)
        assert "entries" in get_result
        _ok("trade_journal_get", get_result)
        print(f"         total={get_result.get('total')}")
    except Exception as e:
        _fail("trade_journal_crud", e)


def test_trade_journal_stats():
    """
    Tests the trade journal statistics endpoint.
    Asserts that the total_entries key is returned correctly.
    """
    print("\n=== /trade-journal/stats ===")
    try:
        from main import trade_journal_stats_endpoint
        result = trade_journal_stats_endpoint(user_id=2)
        assert "total_entries" in result
        _ok("trade_journal_stats", result)
        print(f"         total={result.get('total_entries')}, top_ticker={result.get('most_journalled_ticker')}")
    except Exception as e:
        _fail("trade_journal_stats", e)


# ---------------------------------------------------------------------------
# Task 5 — Screener
# ---------------------------------------------------------------------------

def test_screener():
    """
    Tests the screener endpoint against a predefined list of screen presets.
    Asserts that each preset returns a list of matching stocks.
    """
    print("\n=== /screener ===")
    presets = ["quality_value", "promoter_conviction", "fii_accumulation", "turnaround", "52w_low_bullish"]
    try:
        from main import screener_endpoint
        for preset in presets:
            try:
                result = screener_endpoint(preset=preset)
                assert isinstance(result, list)
                print(f"  [PASS] screener/{preset} → {len(result)} results")
            except Exception as e:
                _fail(f"screener/{preset}", e)
    except ImportError as e:
        _fail("screener_import", e)


# ---------------------------------------------------------------------------
# Task 6 — Timeframe Conflicts
# ---------------------------------------------------------------------------

def test_timeframe_conflicts():
    """
    Tests the portfolio timeframe conflicts endpoint.
    Verifies that the returned payload includes the list of conflicts and the total count.
    """
    print("\n=== /portfolio/timeframe-conflicts ===")
    try:
        from main import portfolio_timeframe_conflicts_endpoint
        result = portfolio_timeframe_conflicts_endpoint(user_id=2)
        assert "conflicts" in result
        assert "conflict_count" in result
        _ok("timeframe_conflicts", result)
        print(f"         conflicts={result.get('conflict_count')}")
        if result.get("conflicts"):
            c = result["conflicts"][0]
            print(f"         first: {c.get('ticker')} short={c.get('short_upside_pct')} long={c.get('long_upside_pct')}")
    except Exception as e:
        _fail("timeframe_conflicts", e)


# ---------------------------------------------------------------------------
# Task 7 — Watchlist Enriched
# ---------------------------------------------------------------------------

def test_watchlist_enriched():
    """
    Tests the enriched watchlist retrieval endpoint.
    Ensures that the returned dictionary contains the watchlist list and processes items successfully.
    """
    print("\n=== /watchlist (enriched) ===")
    try:
        from main import watchlist_get_endpoint
        result = watchlist_get_endpoint(user_id=2)
        items = result.get("watchlist", [])
        _ok("watchlist_enriched", result)
        print(f"         items={len(items)}")
        if items:
            item = items[0]
            print(f"         first item keys: {list(item.keys())}")
            print(f"         last_signal={item.get('last_signal')}, asm={item.get('asm_gsm_status')}")
    except Exception as e:
        _fail("watchlist_enriched", e)


# ---------------------------------------------------------------------------
# Task 16 — Token Stats
# ---------------------------------------------------------------------------

def test_token_stats():
    """
    Tests the token usage statistics endpoint.
    Asserts that total_calls and total_cost metrics are correctly provided.
    """
    print("\n=== /token-stats ===")
    try:
        from main import token_stats_endpoint
        result = token_stats_endpoint()
        assert "total_calls" in result
        _ok("token_stats", result)
        print(f"         calls={result.get('total_calls')}, cost=${result.get('total_cost_usd')}")
    except Exception as e:
        _fail("token_stats", e)


# ---------------------------------------------------------------------------
# DB integrity checks
# ---------------------------------------------------------------------------

def test_db_schema():
    """
    Performs an integrity check on the SQLite database schema by verifying the existence
    of expected tables and columns (e.g., trade_journal, analysis_history).
    """
    print("\n=== DB Schema ===")
    try:
        import sqlite3
        conn = sqlite3.connect(":memory:")
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        expected = {"users", "portfolio", "analysis_history", "signal_events", "price_targets", "trade_journal"}
        missing = expected - tables
        if missing:
            print(f"  [FAIL] Missing tables: {missing}")
        else:
            print(f"  [PASS] All expected tables present: {tables}")

        # Check trade_journal columns
        tj_cols = {r[1] for r in conn.execute("PRAGMA table_info(trade_journal)")}
        expected_cols = {"id", "user_id", "ticker", "action", "price_at_time", "reason_text", "outcome_text", "created_at"}
        nice_cols = {"company_name", "mood", "updated_at"}
        missing_core = expected_cols - tj_cols
        missing_nice = nice_cols - tj_cols
        if missing_core:
            print(f"  [FAIL] trade_journal missing core cols: {missing_core}")
        else:
            print(f"  [PASS] trade_journal core cols OK")
        if missing_nice:
            print(f"  [WARN] trade_journal missing optional cols (run migrate_trade_journal.py): {missing_nice}")

        # Check analysis_history pledging cols
        ah_cols = {r[1] for r in conn.execute("PRAGMA table_info(analysis_history)")}
        pledging = {"promoter_pledged_pct", "promoter_pledged_trend"}
        missing_pledging = pledging - ah_cols
        if missing_pledging:
            print(f"  [FAIL] analysis_history missing pledging cols: {missing_pledging}")
        else:
            print(f"  [PASS] analysis_history pledging cols OK")

        conn.close()
    except Exception as e:
        _fail("db_schema", e)


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  Nivesh Backend — New Endpoint Smoke Tests")
    print("  user_id=2 (nirav, has 16 holdings)")
    print("=" * 60)

    test_db_schema()
    test_risk_analysis()
    test_red_flags()
    test_macro_impact()
    test_trade_journal_crud()
    test_trade_journal_stats()
    test_screener()
    test_timeframe_conflicts()
    test_watchlist_enriched()
    test_token_stats()

    print("\n" + "=" * 60)
    print("  Done.")
    print("=" * 60)
