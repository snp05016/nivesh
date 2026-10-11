"""Admin rights and password resets for existing accounts (AUTH-01).

Admin is the persisted users.is_admin flag; nothing grants it by username.
Run from backend/ after `alembic upgrade head`:
    ../venv/bin/python scripts/manage_users.py check-default-passwords
    ../venv/bin/python scripts/manage_users.py reset-password <username>
    ../venv/bin/python scripts/manage_users.py set-admin <username>
    ../venv/bin/python scripts/manage_users.py revoke-admin <username>

reset-password prompts twice (getpass). Passwords and hashes are never printed.
"""
import argparse
import getpass
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from models.db_models import User  # noqa: E402

# Passwords this repo published for these accounts (the removed init_db seed,
# populate_portfolio.py, reset_mock_user.py). An account still using one is open to anyone.
PUBLISHED_PASSWORDS = {
    "saumya": ("123", "StrongPass@123"),
    "nirav": ("123",),
    "ankur": ("123",),
}
# Same policy as services/auth_service.py (not imported: it pulls in the whole app).
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_BYTES = 72


def _user_query(session, username: str):
    query = session.query(User).filter(User.username == username.lower().strip())
    if query.first() is None:
        raise LookupError(f"no such user: {username}")
    return query


def set_admin(session, username: str, value: bool) -> None:
    _user_query(session, username).update({"is_admin": value})
    session.commit()


def reset_password(session, username: str, password: str) -> None:
    """Store a new bcrypt hash and bump token_version (JWT revocation, AUTH-13)."""
    from database import _hash_password
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"password must be at least {PASSWORD_MIN_LENGTH} characters")
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(f"password must be at most {PASSWORD_MAX_BYTES} bytes")
    _user_query(session, username).update(
        {"password_hash": _hash_password(password), "token_version": User.token_version + 1}
    )
    session.commit()


def accounts_with_published_password(session) -> list:
    from database import verify_password
    hits = []
    for username, passwords in PUBLISHED_PASSWORDS.items():
        row = session.query(User.password_hash).filter(User.username == username).first()
        if row is not None and any(verify_password(p, row.password_hash) for p in passwords):
            hits.append(username)
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Admin rights and password resets.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("set-admin", "revoke-admin", "reset-password"):
        sub.add_parser(name).add_argument("username")
    sub.add_parser("check-default-passwords")
    args = parser.parse_args()

    # Resolve DATABASE_URL like the service does (WorkingDirectory=backend, backend/.env).
    os.chdir(BACKEND)
    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env", override=False)
    from database import get_session  # reads DATABASE_URL at import, so after .env

    with get_session() as session:
        try:
            if args.command == "check-default-passwords":
                hits = accounts_with_published_password(session)
                for username in hits:
                    print(f"DEFAULT PASSWORD: {username}")
                if hits:
                    print("Run reset-password for each account above, or delete it if unused.")
                    return 1
                print("No account uses a published default password.")
                return 0
            if args.command == "reset-password":
                password = getpass.getpass("New password: ")
                if password != getpass.getpass("Repeat new password: "):
                    raise ValueError("passwords do not match")
                reset_password(session, args.username, password)
                print(f"Password reset for {args.username}.")
                return 0
            set_admin(session, args.username, args.command == "set-admin")
            print(f"{args.username}: is_admin={args.command == 'set-admin'}")
            return 0
        except (LookupError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
