from fastapi import APIRouter, Depends, Request, HTTPException
from core.security import require_auth
from helpers import (
    LoginRequest, RegisterRequest, _check_rate_limit
)
from schemas.auth import ChangePasswordRequest
from services.auth_service import change_password, login_user, logout_all, register_user

router = APIRouter(tags=["Authentication"])


@router.post("/login")
def login_endpoint(req: LoginRequest):
    # Per-account limit on top of the per-IP one, so spraying one account from many IPs is capped (AUTH-23).
    _check_rate_limit(f"login:{req.username}", "/login", "POST")
    try:
        return login_user(req.username, req.password)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/register")
def register_endpoint(req: RegisterRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    # The security middleware already limits POST /register per client IP.
    try:
        return register_user(
            req.username, req.password, req.display_name,
            accepted_policy_version=req.accepted_policy_version,
            age_confirmed=req.age_confirmed,
            ip_address=client_ip if request.client else None,
            app_version=(request.headers.get("x-app-version") or "")[:20] or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/auth/logout")
def logout_endpoint(user_id: int = Depends(require_auth)):
    """Sign out everywhere: every token issued to this user stops working (AUTH-13)."""
    logout_all(user_id)
    return {"status": "logged_out"}


@router.post("/api/v1/auth/change-password")
def change_password_endpoint(req: ChangePasswordRequest, user_id: int = Depends(require_auth)):
    """Change the password and revoke every existing token, this one included (AUTH-13)."""
    _check_rate_limit(f"change-password:{user_id}", "/login", "POST")
    try:
        change_password(user_id, req.current_password, req.new_password)
    except (PermissionError, ValueError) as e:
        # 400, not 401: a mistyped current password must not look like an expired session.
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "password_changed"}
