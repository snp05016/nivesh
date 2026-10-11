from fastapi import APIRouter, Request, HTTPException
from helpers import (
    LoginRequest, RegisterRequest, _check_rate_limit
)
from services.auth_service import login_user, register_user

router = APIRouter(tags=["Authentication"])


@router.post("/login")
def login_endpoint(req: LoginRequest):
    try:
        return login_user(req.username, req.password)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/register")
def register_endpoint(req: RegisterRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    reg_key = f"reg_{client_ip}"
    _check_rate_limit(reg_key, "/register")
    
    try:
        return register_user(req.username, req.password, req.display_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
