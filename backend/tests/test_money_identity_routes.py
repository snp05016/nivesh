"""FINSEC-27: coverage gate for the money and identity routes.

Every route under the loan, KYC, account, FD, subscription and compliance
routers must be exercised by at least one backend test module, so a new money
or identity endpoint cannot ship without a test. Auth on these routes is
checked by test_route_auth_inventory.py; behaviour by the per-router modules
(test_finance_loans, test_kyc_consent_api, test_fixed_deposits_api,
test_subscription_compliance_api, test_key_fact_statement, ...).
"""
from pathlib import Path

from fastapi.routing import APIRoute

from main import app

MONEY_IDENTITY_PREFIXES = (
    "/api/v1/finance", "/api/v1/kyc", "/api/v1/me", "/api/v1/fixed-deposits",
    "/api/v1/subscription", "/api/v1/compliance",
)
_TESTS_DIR = Path(__file__).resolve().parent


def _test_sources() -> str:
    me = Path(__file__).resolve()
    return "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in _TESTS_DIR.rglob("test_*.py")
        if p.resolve() != me
    )


def _money_routes() -> list[tuple[str, str]]:
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and any(
            route.path == p or route.path.startswith(p + "/") for p in MONEY_IDENTITY_PREFIXES
        ):
            for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                routes.append((method, route.path))
    return routes


def test_money_identity_routes_found():
    assert len(_money_routes()) >= 30


def test_every_money_identity_route_has_a_test():
    sources = _test_sources()
    untested = []
    for method, path in _money_routes():
        # Literal part before the first path parameter; tests may call either
        # the /api/v1/<name> path or its deprecated /api/<name> alias.
        static = path.split("{")[0].rstrip("/")
        if static not in sources and static.replace("/api/v1/", "/api/", 1) not in sources:
            untested.append(f"{method} {path}")
    assert not untested, f"money/identity routes without any test: {untested}"
