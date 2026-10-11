"""JWT authentication and authorization dependencies.

Extracted from main.py during monolith refactor Phase 2. helpers.py re-exports
these, so there is one implementation. There is no operator/admin token bypass
(AUTH-02): admin routes need the JWT of a users.is_admin account.
"""

from typing import Optional
from fastapi import HTTPException, Header
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
