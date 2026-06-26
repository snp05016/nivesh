import logging
#!/usr/bin/env python3
"""
Smoke test all safe GET endpoints by importing the FastAPI app and using
the TestClient. Skips auth-protected and mutation endpoints.
Never touches production DB.

Exit 0 = all tested endpoints responded (even if 404/422 — checks for 500s).
Exit 1 = unexpected 500s found.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "sqlite:///./stockapp_health_check_test.db")
os.environ.setdefault("ENABLE_SCHEDULER", "false")
os.environ.setdefault("JWT_SECRET", "health-check-test")

# Create a minimal DB for the smoke test
try:
    from database import init_db
    init_db()
except Exception:
    pass

try:
    from fastapi.testclient import TestClient
    import main as app_module
    app = app_module.app
    client = TestClient(app, raise_server_exceptions=False)
except Exception as e:
    logging.info(f"[FAIL] Cannot create TestClient: {e}")
    sys.exit(1)

# Safe GET endpoints to smoke — no auth required, no path params that need real data
SAFE_ENDPOINTS = [
    "/ping",
    "/health",
    "/favicon.ico",
    "/api/v1/watchlist?user_id=999999",        # non-existent user → empty list or 404
    "/api/v1/morning-brief?user_id=999999",     # non-existent user → handled gracefully
    "/api/v1/market/pulse",                     # market data endpoint
    "/api/v1/market/earnings-calendar",
    "/api/v1/market/block-deals",
    "/api/v1/market/macro-events",
]

failures: list[str] = []
tested = 0

for endpoint in SAFE_ENDPOINTS:
    try:
        resp = client.get(endpoint)
        tested += 1
        if resp.status_code == 500:
            failures.append(f"GET {endpoint} → 500: {resp.text[:200]}")
            logging.info(f"  [FAIL] GET {endpoint} → 500")
        else:
            logging.info(f"  [OK]   GET {endpoint} → {resp.status_code}")
    except Exception as e:
        failures.append(f"GET {endpoint} → exception: {e}")
        logging.info(f"  [FAIL] GET {endpoint} → exception: {e}")

logging.info(f"\n[OK] Tested {tested} endpoints")

if failures:
    logging.info(f"[FAIL] {len(failures)} endpoints returned 500:")
    for f in failures:
        logging.info(f"  {f}")
    sys.exit(1)

logging.info("[OK] No unexpected 500s found")
sys.exit(0)
