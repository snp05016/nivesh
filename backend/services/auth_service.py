from helpers import get_session, get_user_by_credentials, User, create_access_token
from database import create_user as _create_user
from services.kyc_consent_service import record_consent


def _auth_payload(user) -> dict:
    # Login and register must share one shape: iOS decodes both into LoggedInUser,
    # which requires access_token (CMON-01).
    return {
        "user_id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
    }


def login_user(username, password):
    with get_session() as session:
        user = get_user_by_credentials(session, username, password)
        if not user:
            raise PermissionError("Invalid username or password")
        return _auth_payload(user)

PASSWORD_MIN_LENGTH = 8
# bcrypt only accepts 72 bytes (bcrypt>=5 raises on longer input, which
# create_user would swallow into a 500), so cap at 72 UTF-8 bytes.
PASSWORD_MAX_BYTES = 72


def register_user(username, password, display_name, accepted_policy_version=None, ip_address=None, app_version=None):
    # Password policy; ValueError surfaces as HTTP 400 with this text as `detail`.
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters.")
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(f"Password must be at most {PASSWORD_MAX_BYTES} characters.")
    with get_session() as session:
        existing = session.query(User).filter_by(username=username.lower()).first()
        if existing:
            raise ValueError("Username already exists")
        
        user = _create_user(session, username, password, display_name)
        if not user:
            raise RuntimeError("Failed to create user")
        payload = _auth_payload(user)

    # FINSEC-09: server-side record of the notice the user accepted at sign-up.
    # Older clients send no version, so there is nothing to record for them.
    if accepted_policy_version:
        for consent_type in ("privacy_notice", "terms"):
            record_consent(
                payload["user_id"], consent_type, True,
                ip_address=ip_address,
                policy_version=accepted_policy_version,
                app_version=app_version,
            )
    return payload
