import hashlib
import logging

from helpers import get_session, get_user_by_credentials, User, DeviceToken, create_access_token
from database import create_user as _create_user, _hash_password, verify_password
from services.audit_service import audit
from services.disclosure_service import CURRENT_POLICY_VERSION
from services.kyc_consent_service import record_consent


def _auth_payload(user) -> dict:
    # Login and register must share one shape: iOS decodes both into LoggedInUser,
    # which requires access_token (CMON-01).
    return {
        "user_id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "access_token": create_access_token(user.id, user.token_version or 0),
        "token_type": "bearer",
    }


_auth_log = logging.getLogger("nivesh.auth")


def _username_digest(username: str) -> str:
    return hashlib.sha256(username.strip().lower().encode()).hexdigest()[:16]


def _audit_auth(session, user_id, action):
    # FINSEC-22: an audit failure must never block sign-in or sign-up.
    try:
        audit(session, user_id, action)
        session.commit()
    except Exception as exc:
        session.rollback()
        _auth_log.warning("auth.audit_failed action=%s user_id=%s: %s", action, user_id, type(exc).__name__)


def login_user(username, password):
    with get_session() as session:
        user = get_user_by_credentials(session, username, password)
        if not user:
            # AUTH-23: audit trail for brute force, without the raw username or password.
            _auth_log.warning("auth.login_failed user=%s", _username_digest(username))
            raise PermissionError("Invalid username or password")
        payload = _auth_payload(user)
        _audit_auth(session, payload["user_id"], "login")
        return payload

PASSWORD_MIN_LENGTH = 8
# bcrypt only accepts 72 bytes (bcrypt>=5 raises on longer input, which
# create_user would swallow into a 500), so cap at 72 UTF-8 bytes.
PASSWORD_MAX_BYTES = 72


def _check_password_policy(password):
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters.")
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(f"Password must be at most {PASSWORD_MAX_BYTES} characters.")


def _revoke_sessions(session, user_id, extra=None):
    """Bump users.token_version so every issued token fails verify_access_token, and
    drop the push bindings of those signed-out devices (iOS re-registers on login)."""
    session.query(User).filter(User.id == user_id).update(
        {"token_version": User.token_version + 1, **(extra or {})}, synchronize_session=False
    )
    session.query(DeviceToken).filter(DeviceToken.user_id == user_id).delete(synchronize_session=False)
    session.commit()


def logout_all(user_id):
    """Sign the user out on every device (AUTH-13)."""
    with get_session() as session:
        _revoke_sessions(session, user_id)


def change_password(user_id, current_password, new_password):
    """Set a new password and revoke all existing tokens (AUTH-13).

    PermissionError when current_password is wrong; ValueError when the new one
    breaks the registration password policy.
    """
    _check_password_policy(new_password)
    with get_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if not user or not verify_password(current_password or "", str(user.password_hash)):
            _auth_log.warning("auth.change_password_failed user_id=%s", user_id)
            raise PermissionError("Current password is incorrect")
        _revoke_sessions(session, user_id, {"password_hash": _hash_password(new_password)})


def update_display_name(user_id, display_name):
    """Set the user's display name (GH-692). None when the user no longer exists."""
    with get_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        user.display_name = display_name
        session.commit()
        return {"user_id": user.id, "username": user.username, "display_name": user.display_name}


def register_user(username, password, display_name, accepted_policy_version=None, age_confirmed=False, ip_address=None, app_version=None):
    # REG-12: no account without consent to the current notice and an 18+
    # attestation. ValueError surfaces as HTTP 400 with this text as `detail`.
    if accepted_policy_version != CURRENT_POLICY_VERSION:
        raise ValueError("Please update the app and accept the current Privacy Policy and Terms of Use.")
    if age_confirmed is not True:
        raise ValueError("You must be 18 or older to create an account.")
    _check_password_policy(password)
    with get_session() as session:
        username = username.strip().lower()  # create_user and login use the same form (AUTH-23)
        existing = session.query(User).filter_by(username=username).first()
        if existing:
            raise ValueError("Username already exists")
        
        user = _create_user(session, username, password, display_name)
        if not user:
            raise RuntimeError("Failed to create user")
        payload = _auth_payload(user)
        _audit_auth(session, payload["user_id"], "account_registered")

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
