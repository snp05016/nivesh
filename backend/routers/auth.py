from fastapi import APIRouter, Request, HTTPException
from helpers import (
    LoginRequest, RegisterRequest, _check_rate_limit
)
from services.auth_service import login_user, register_user

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
