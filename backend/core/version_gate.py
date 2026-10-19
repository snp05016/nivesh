"""HTTP 426 gate for iOS builds below the minimum (I11 rollout lever for C3/I03).

Registered last in main.py, so it runs outermost: an old build sees 426 before
the legacy 410 gate and before the rate limiter. Off unless
ios_config.ios_min_build() > 0 (config/feature_flags.py serves 0 unless the
minimum-build and App Store URL env values are both valid). Only iOS clients are gated:
browsers, curl, tests and the admin dashboard always pass.

Every build shipped so far reports build 1; never raise the minimum build
before the release that carries real build numbers (trust-build-number) is live.
"""

from __future__ import annotations

import importlib.util
import logging
import re
from collections.abc import Awaitable, Callable, Mapping
from types import ModuleType

from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

logger = logging.getLogger("nivesh.version_gate")

ios_config: ModuleType | None
try:
    # The single source of the minimum build; app-config's ios.min_build uses it too.
    from config import feature_flags as ios_config  # pyright: ignore[reportAttributeAccessIssue]  (config/feature_flags.py ships with ios-flags-be)
except ImportError:  # 'cannot import name' from the existing config package, not ModuleNotFoundError
    if importlib.util.find_spec("config.feature_flags") is not None:
        raise  # the file exists but is broken: that must not silently disable the gate
    ios_config = None  # ios-flags-be not deployed yet: the gate stays off
    logger.warning("config.feature_flags missing; iOS version gate disabled")

UPDATE_TEXT = "This version of Nivesh is no longer supported. Please update Nivesh from the App Store."

EXEMPT_PREFIXES = (
    "/api/v1/app-config",
    "/api/v1/flags",
    "/api/v1/features",
    "/health",
    "/ping",
    "/api/v1/ping",
    "/favicon.ico",
)

# '<App>/<CFBundleVersion> CFNetwork/x Darwin/y' (default URLSession user agent).
_UA_BUILD = re.compile(r"([^/\s]+)/(\d+)")


def client_build(headers: Mapping[str, str]) -> int | None:
    """The iOS build number a request reports, or None for a non-iOS client."""
    build = (headers.get("x-app-build") or "").strip()
    if build.isascii() and build.isdigit():
        return int(build)
    ua = headers.get("user-agent") or ""
    if "CFNetwork" not in ua:
        return None
    m = _UA_BUILD.match(ua)
    # A bare 'CFNetwork/1494 ...' carries no app build: treat it as 0.
    return int(m.group(2)) if m and m.group(1) != "CFNetwork" else 0


async def version_gate(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """426 plain text for iOS builds below ios_min_build(); pass everything else through."""
    min_build = ios_config.ios_min_build() if ios_config is not None else 0  # per request
    if (
        min_build > 0
        and request.method != "OPTIONS"
        and not request.url.path.startswith(EXEMPT_PREFIXES)
    ):
        build = client_build(request.headers)
        if build is not None and build < min_build:
            return PlainTextResponse(UPDATE_TEXT, status_code=426, headers={"Cache-Control": "no-store"})
    return await call_next(request)
