from fastapi import APIRouter, Request
from helpers import (
    LoginRequest, RegisterRequest, _check_rate_limit
)
from services.auth_service import login_user, register_user

router = APIRouter(tags=["Authentication"])


@router.post("/login")
def login_endpoint(req: LoginRequest):
    return login_user(req.username, req.password)


@router.post("/register")
def register_endpoint(req: RegisterRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    reg_key = f"reg_{client_ip}"
    _check_rate_limit(reg_key, "/auth/register")
    return register_user(req.username, req.password, req.display_name)
