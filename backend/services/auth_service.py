import hashlib
import logging

from helpers import get_session, get_user_by_credentials, User, create_access_token
from database import create_user as _create_user
from services.disclosure_service import CURRENT_POLICY_VERSION
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


_auth_log = logging.getLogger("nivesh.auth")


def _username_digest(username: str) -> str:
    return hashlib.sha256(username.strip().lower().encode()).hexdigest()[:16]


def login_user(username, password):
    with get_session() as session:
        user = get_user_by_credentials(session, username, password)
        if not user:
            # AUTH-23: audit trail for brute force, without the raw username or password.
            _auth_log.warning("auth.login_failed user=%s", _username_digest(username))
            raise PermissionError("Invalid username or password")
        return _auth_payload(user)

PASSWORD_MIN_LENGTH = 8
# bcrypt only accepts 72 bytes (bcrypt>=5 raises on longer input, which
# create_user would swallow into a 500), so cap at 72 UTF-8 bytes.
PASSWORD_MAX_BYTES = 72


def register_user(username, password, display_name, accepted_policy_version=None, age_confirmed=False, ip_address=None, app_version=None):
    # REG-12: no account without consent to the current notice and an 18+
    # attestation. ValueError surfaces as HTTP 400 with this text as `detail`.
    if accepted_policy_version != CURRENT_POLICY_VERSION:
        raise ValueError("Please update the app and accept the current Privacy Policy and Terms of Use.")
    if age_confirmed is not True:
        raise ValueError("You must be 18 or older to create an account.")
    # Password policy.
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters.")
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(f"Password must be at most {PASSWORD_MAX_BYTES} characters.")
    with get_session() as session:
        username = username.strip().lower()  # create_user and login use the same form (AUTH-23)
        existing = session.query(User).filter_by(username=username).first()
        if existing:
            raise ValueError("Username already exists")
        
        user = _create_user(session, username, password, display_name)
        if not user:
            raise RuntimeError("Failed to create user")
        payload = _auth_payload(user)

    # FINSEC-09 / REG-12: server-side record of the notice and the age
    # attestation the user accepted at sign-up.
    for consent_type in ("privacy_notice", "terms", "age_18_plus"):
        record_consent(
            payload["user_id"], consent_type, True,
            ip_address=ip_address,
            policy_version=accepted_policy_version,
            app_version=app_version,
        )
    return payload
