"""JWT authentication and authorization dependencies.

Extracted from main.py during monolith refactor Phase 2. helpers.py re-exports
these, so there is one implementation. There is no operator/admin token bypass
(AUTH-02): admin routes need the JWT of a users.is_admin account.
"""

from typing import Optional
from fastapi import Depends, HTTPException, Header
from core import rate_limiter
from database import verify_access_token, is_admin


def get_current_user_id(authorization: str = Header(None)) -> Optional[int]:
    """Extract user_id from Bearer token. Returns None if missing/invalid."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    return verify_access_token(token)


def require_auth(authorization: str = Header(None)) -> int:
    """Require valid JWT token. Raises 401 if missing/invalid."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = authorization.split(" ", 1)[1]
    user_id = verify_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id


def require_admin(authorization: str = Header(None)) -> int:
    """Require valid JWT token + admin role. Raises 401/403 otherwise."""
    user_id = require_auth(authorization)
    if not is_admin(user_id):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id


def rate_limited_user(bucket: str):
    """Dependency: require_auth plus a per-user limit on a core.rate_limiter bucket.

    Use on write endpoints that create identity/money rows (FINSEC-23); 429 with
    Retry-After once the user exceeds the bucket's _RATE_LIMITS entry.
    """
    def _dep(user_id: int = Depends(require_auth)) -> int:
        # Module-attribute lookup, so tests can patch core.rate_limiter._check_rate_limit.
        rate_limiter._check_rate_limit(f"user:{user_id}", bucket)
        return user_id
    return _dep


def assert_same_user(user_id: int, uid: int) -> None:
    """Raise 403 when an authenticated caller (uid) acts on another user's data."""
    if user_id != uid:
        raise HTTPException(status_code=403, detail="Forbidden")


def require_user_match(user_id: int, uid: int = Depends(require_auth)) -> int:
    """Require a valid JWT whose user is the route's `user_id` (path or query param).

    401 when the token is missing/invalid, 403 when it belongs to someone else.
    """
    assert_same_user(user_id, uid)
    return uid
