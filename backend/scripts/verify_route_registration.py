#!/usr/bin/env python3
"""
Verify FastAPI route registration — all routers imported, no duplicate operation IDs,
no broken route handlers, all routes enumerable.

Exit 0 = healthy.
Exit 1 = issues found.
"""

import logging
import os
import sys
from pathlib import Path

# Paths as actually registered (routers are mounted without a prefix).
CRITICAL_PATHS = {
    "/ping", "/health", "/analyze", "/analyze/job/{job_id}",
    "/portfolio/{user_id}", "/watchlist/{user_id}",
}


def find_route_issues(app) -> list[str]:
    routes = list(app.routes)
    if not routes:
        return ["No routes registered on app"]

    issues = []

    # Check for duplicate operation IDs
    seen_op_ids: dict[str, list[str]] = {}
    for route in routes:
        if hasattr(route, "operation_id") and route.operation_id:
            seen_op_ids.setdefault(route.operation_id, []).append(getattr(route, "path", "?"))
    for op_id, paths in seen_op_ids.items():
        if len(paths) > 1:
            issues.append(f"Duplicate operation_id '{op_id}' on routes: {paths}")

    # Check that every route has a callable endpoint
    broken = [getattr(r, "path", "?") for r in routes
              if hasattr(r, "endpoint") and not callable(r.endpoint)]
    if broken:
        issues.append(f"Non-callable endpoints on routes: {broken}")

    # Spot-check critical routes exist
    registered_paths = {getattr(r, "path", "") for r in routes}
    for p in sorted(CRITICAL_PATHS - registered_paths):
        issues.append(f"Critical route missing: {p}")

    return issues


def main() -> int:
    # Configure before importing main.py: nothing else sets up logging here, and
    # the default WARNING level would hide every [OK]/[FAIL] line.
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.path.insert(0, str(Path(__file__).parent.parent))
    os.environ.setdefault("DATABASE_URL", "sqlite:///./stockapp_health_check_test.db")
    os.environ.setdefault("ENABLE_SCHEDULER", "false")
    os.environ.setdefault("ENVIRONMENT", "test")  # unset counts as production (OPS-13)
    os.environ.setdefault("JWT_SECRET", "health-check-secret")

    try:
        import main as app_module
        app = app_module.app
    except Exception as e:
        logging.info(f"[FAIL] Cannot import main.py: {e}")
        return 1

    logging.info(f"[OK] {len(app.routes)} routes registered")
    issues = find_route_issues(app)
    if issues:
        for issue in issues:
            logging.info(f"[FAIL] {issue}")
        return 1

    logging.info("[OK] Route registration healthy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
