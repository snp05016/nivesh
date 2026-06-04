from fastapi import APIRouter, HTTPException, Request
from helpers import (
    get_session, get_user_by_credentials, User, create_access_token,
    LoginRequest, RegisterRequest, _check_rate_limit
)
from database import create_user as _create_user

router = APIRouter(tags=["Authentication"])


@router.post("/login")
def login_endpoint(req: LoginRequest):
    with get_session() as session:
        user = get_user_by_credentials(session, req.username, req.password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        token = create_access_token(user.id)
        return {
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "access_token": token,
            "token_type": "bearer",
        }


@router.post("/register")
def register_endpoint(req: RegisterRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    reg_key = f"reg_{client_ip}"
    if not _check_rate_limit(reg_key):
        raise HTTPException(status_code=429, detail="Too many registration attempts. Try again later.")
    with get_session() as session:
        existing = session.query(User).filter_by(username=req.username.lower()).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")
        
        user = _create_user(session, req.username, req.password, req.display_name)
        if not user:
            raise HTTPException(status_code=500, detail="Failed to create user")
        
        return {"user_id": user.id, "username": user.username, "display_name": user.display_name}
