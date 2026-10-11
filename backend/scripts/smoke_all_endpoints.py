#!/usr/bin/env python3
"""
Smoke test hermetic GET endpoints by importing the FastAPI app and using
the TestClient. Only routes that make no network calls are listed; auth-
protected routes are hit without a token and must reject with 401.
Never touches production DB.

Exit 0 = every endpoint returned its expected status.
Exit 1 = any status mismatch (including 404/422) or exception.
"""

import os
import sys
from pathlib import Path

# (path, expected status). Keep this list hermetic: no yfinance, scraping or LLM.
ENDPOINTS: list[tuple[str, int]] = [
    ("/ping", 200),
    ("/health", 200),
    ("/health/live", 200),
    ("/favicon.ico", 200),
    ("/watchlist/999999", 401),
    ("/morning-summary/999999", 401),
    ("/portfolio/999999", 401),
    ("/trade-journal/999999", 401),
]


def main() -> int:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    os.environ.setdefault("DATABASE_URL", "sqlite:///./stockapp_health_check_test.db")
    os.environ.setdefault("ENABLE_SCHEDULER", "false")
    os.environ.setdefault("JWT_SECRET", "health-check-test")

    try:
        from database import init_db
        init_db()
    except Exception as e:
        print(f"[WARN] init_db failed: {e}", file=sys.stderr)

    try:
        from fastapi.testclient import TestClient
        import main as app_module
        client = TestClient(app_module.app, raise_server_exceptions=False)
    except Exception as e:
        print(f"[FAIL] Cannot create TestClient: {e}", file=sys.stderr)
        return 1

    failures: list[str] = []
    for path, expected in ENDPOINTS:
        try:
            status = client.get(path).status_code
        except Exception as e:
            failures.append(f"GET {path} -> exception: {e}")
            continue
        if status == expected:
            print(f"  [OK]   GET {path} -> {status}")
        else:
            failures.append(f"GET {path} -> {status} (expected {expected})")

    for f in failures:
        print(f"  [FAIL] {f}", file=sys.stderr)
    print(f"\nTested {len(ENDPOINTS)} endpoints, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
