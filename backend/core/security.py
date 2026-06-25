"""JWT authentication and authorization dependencies.

Extracted from main.py during monolith refactor Phase 2.
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


"""Core security utilities — JWT auth, admin controls, rate limiting."""
import os
from fastapi import HTTPException, Header, status

from database import verify_access_token, is_admin


def require_auth(authorization: str = Header(None)) -> int:
    """Require valid JWT token. Raises 401 if missing/invalid."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = authorization.split(" ", 1)[1]

    # Dev bypass — ONLY when ADMIN_TOKEN env var is set (never in production)
    admin_override = os.getenv("ADMIN_TOKEN")
    if admin_override and token == admin_override:
        return 1

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
