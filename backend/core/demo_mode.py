"""FastAPI dependency that hides demo-only routes unless DEMO_MODE is on.

The loan marketplace (hash-based mock credit score), demo bank links, the demo
finance tracker, demo FD schemes/bookings and the mock KYC fraud-signal summary
write to real tables but are illustrations, not integrations. Production keeps
DEMO_MODE=false, so these routes answer 404 there.

Usage:

    router = APIRouter(prefix="/api/x", dependencies=[Depends(require_demo_mode)])
"""
from fastapi import HTTPException

import config.settings


def require_demo_mode() -> None:
    # Read at call time (module attribute, not an imported name) so tests can
    # monkeypatch config.settings.DEMO_MODE.
    if not config.settings.DEMO_MODE:
        raise HTTPException(status_code=404, detail="Not found")
