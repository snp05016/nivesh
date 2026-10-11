"""ARCH-14: market.py / portfolio.py were split into domain routers without changing any path.

Every moved (method, path) must still be registered, and a concrete request to it must be
served by the handler in its new module (not swallowed by an earlier param route such as
GET /portfolio/{user_id}). test_route_table.py guards shadowing in general.
"""
import re

from fastapi.routing import APIRoute
from starlette.routing import Match

from main import app

MOVED = [
    ("POST", "/portfolio/sip-calculator", "routers.portfolio_analytics.sip_calculator"),
    ("GET", "/portfolio/benchmark", "routers.portfolio_analytics.portfolio_benchmark"),
    ("GET", "/portfolio/signal-warnings", "routers.portfolio_analytics.portfolio_signal_warnings"),
    ("GET", "/api/v1/portfolio/valuation-history", "routers.portfolio_analytics.get_valuation_history"),
    ("GET", "/api/v1/portfolio/charts/{user_id}/image/{filename}", "routers.portfolio_analytics.portfolio_chart_image"),
    ("GET", "/api/v1/portfolio/charts/{user_id}", "routers.portfolio_analytics.portfolio_charts_endpoint"),
    ("GET", "/portfolio/risk-analysis/{user_id}", "routers.portfolio_analytics.portfolio_risk_analysis_endpoint"),
    ("GET", "/portfolio/red-flags/{user_id}", "routers.portfolio_analytics.portfolio_red_flags_endpoint"),
    ("GET", "/macro-impact/{user_id}", "routers.portfolio_analytics.macro_impact_endpoint"),
    ("GET", "/portfolio/timeframe-conflicts/{user_id}", "routers.portfolio_analytics.portfolio_timeframe_conflicts_endpoint"),
    ("GET", "/api/v1/market/net-worth-ledger/{user_id}", "routers.portfolio_analytics.net_worth_ledger_endpoint"),
    ("GET", "/attribution/{user_id}", "routers.portfolio_analytics.portfolio_attribution_endpoint"),
    ("GET", "/signal-accuracy", "routers.portfolio_analytics.get_signal_accuracy"),
    ("GET", "/morning-summary/{user_id}", "routers.morning_brief.morning_summary_endpoint"),
    ("GET", "/api/v1/portfolio/advisor-consensus", "routers.advisor_consensus.portfolio_advisor_consensus"),
    ("GET", "/portfolio/export/excel/{user_id}", "routers.portfolio_exports.export_portfolio_excel"),
    ("GET", "/portfolio/export/pdf/{user_id}", "routers.portfolio_exports.export_portfolio_pdf"),
    ("POST", "/trade-journal", "routers.trade_journal.trade_journal_add_endpoint"),
    ("GET", "/trade-journal/{user_id}", "routers.trade_journal.trade_journal_get_endpoint"),
    ("PUT", "/trade-journal/{entry_id}", "routers.trade_journal.trade_journal_update_endpoint"),
    ("DELETE", "/trade-journal/{entry_id}", "routers.trade_journal.trade_journal_delete_endpoint"),
    ("GET", "/trade-journal/{user_id}/stats", "routers.trade_journal.trade_journal_stats_endpoint"),
    ("GET", "/earnings-calendar", "routers.earnings.earnings_calendar_endpoint"),
    ("GET", "/api/v1/earnings/sync-ratio", "routers.earnings.earnings_sync_ratio_endpoint"),
    ("GET", "/api/v1/earnings/yoy-aggregate", "routers.earnings.yoy_aggregate_endpoint"),
    ("GET", "/api/v1/earnings/progress", "routers.earnings.earnings_progress_endpoint"),
    ("GET", "/api/v1/earnings/feed", "routers.earnings.earnings_feed_endpoint"),
    ("GET", "/api/v1/earnings/calendar", "routers.earnings.earnings_calendar_day_endpoint"),
    ("GET", "/api/v1/earnings/estimates", "routers.earnings.earnings_estimates_endpoint"),
    ("GET", "/api/v1/earnings/post-result-movers", "routers.earnings.post_result_movers_endpoint"),
    ("GET", "/api/v1/earnings/alerts", "routers.earnings.earnings_alerts_get_endpoint"),
    ("POST", "/api/v1/earnings/alerts", "routers.earnings.earnings_alerts_post_endpoint"),
    ("DELETE", "/api/v1/earnings/alerts/{alert_id}", "routers.earnings.earnings_alerts_delete_endpoint"),
    ("GET", "/block-deals/{ticker}", "routers.institutional.block_deals_endpoint"),
    ("GET", "/fii-dii-flow", "routers.institutional.fii_dii_flow_endpoint"),
    ("GET", "/api/v1/market/institutional-flow", "routers.institutional.market_institutional_flow_endpoint"),
    ("GET", "/api/v1/market/institutional-leaderboard", "routers.institutional.institutional_leaderboard_endpoint"),
    ("GET", "/api/v1/ideas/advisors", "routers.ideas.ideas_advisors_endpoint"),
    ("GET", "/api/v1/ideas/feed", "routers.ideas.ideas_feed_endpoint"),
    ("GET", "/api/v1/admin/error-logs", "routers.admin_errors.admin_error_logs_endpoint"),
    ("GET", "/api/v1/admin/earnings-errors", "routers.admin_errors.admin_earnings_errors_endpoint"),
    ("GET", "/api/v1/admin/ideas-errors", "routers.admin_errors.admin_ideas_errors_endpoint"),
    ("GET", "/fundamentals/piotroski/{ticker}", "routers.fundamentals.piotroski_endpoint"),
]


def _first_match(method, path):
    scope = {"type": "http", "path": path, "method": method, "root_path": ""}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return route
    return None


def test_moved_routes_resolve_to_new_module():
    wrong = []
    for method, template, handler in MOVED:
        concrete = re.sub(r"\{[^}]+\}", "7", template)
        route = _first_match(method, concrete)
        got = f"{route.endpoint.__module__}.{route.endpoint.__name__}" if route else None
        if got != handler or route.path != template:
            wrong.append((method, concrete, got, handler))
    assert not wrong, f"Moved routes resolve to the wrong handler: {wrong}"


def test_user_id_route_still_serves_numeric_ids():
    route = _first_match("GET", "/portfolio/42")
    assert route is not None and route.endpoint.__name__ == "portfolio_endpoint"
