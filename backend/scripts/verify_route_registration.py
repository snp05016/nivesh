import logging
#!/usr/bin/env python3
"""
Verify FastAPI route registration — all routers imported, no duplicate operation IDs,
no broken route handlers, all routes enumerable.

Exit 0 = healthy.
Exit 1 = issues found.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "sqlite:///./stockapp_health_check_test.db")
os.environ.setdefault("ENABLE_SCHEDULER", "false")
os.environ.setdefault("JWT_SECRET", "health-check-secret")

issues = []

try:
    import main as app_module
    app = app_module.app
except Exception as e:
    logging.info(f"[FAIL] Cannot import main.py: {e}")
    sys.exit(1)

# Enumerate all routes
routes = list(app.routes)
if not routes:
    logging.info("[FAIL] No routes registered on app")
    sys.exit(1)

logging.info(f"[OK] {len(routes)} routes registered")

# Check for duplicate operation IDs
seen_op_ids: dict[str, list[str]] = {}
for route in routes:
    if hasattr(route, "operation_id") and route.operation_id:
        op_id = route.operation_id
        path = getattr(route, "path", "?")
        seen_op_ids.setdefault(op_id, []).append(path)

for op_id, paths in seen_op_ids.items():
    if len(paths) > 1:
        issues.append(f"Duplicate operation_id '{op_id}' on routes: {paths}")

# Check that every route has a callable endpoint
broken = []
for route in routes:
    if hasattr(route, "endpoint"):
        ep = route.endpoint
        if not callable(ep):
            broken.append(getattr(route, "path", "?"))

if broken:
    issues.append(f"Non-callable endpoints on routes: {broken}")

# Spot-check critical routes exist
critical_paths = {
    "/ping", "/health", "/api/v1/analyze", "/api/v1/job/{job_id}",
    "/api/v1/portfolio", "/api/v1/watchlist",
}
registered_paths = {getattr(r, "path", "") for r in routes}
for p in critical_paths:
    if p not in registered_paths:
        issues.append(f"Critical route missing: {p}")
    else:
        logging.info(f"[OK] Route registered: {p}")

if issues:
    for issue in issues:
        logging.info(f"[FAIL] {issue}")
    sys.exit(1)

logging.info("[OK] Route registration healthy")
sys.exit(0)
