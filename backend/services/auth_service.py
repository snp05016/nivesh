from helpers import get_session, get_user_by_credentials, User, create_access_token
from database import create_user as _create_user
def login_user(username, password):
    with get_session() as session:
        user = get_user_by_credentials(session, username, password)
        if not user:
            raise PermissionError("Invalid username or password")
        token = create_access_token(user.id)
        return {
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "access_token": token,
            "token_type": "bearer",
        }

def register_user(username, password, display_name):
    with get_session() as session:
        existing = session.query(User).filter_by(username=username.lower()).first()
        if existing:
            raise ValueError("Username already exists")
        
        user = _create_user(session, username, password, display_name)
        if not user:
            raise RuntimeError("Failed to create user")
        
        return {"user_id": user.id, "username": user.username, "display_name": user.display_name}
