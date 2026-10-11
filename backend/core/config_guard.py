"""Fail-closed startup configuration checks (REL-26, SILENT-09).

Production must never boot with a forgeable JWT secret or credentialed wildcard CORS.
"""
from __future__ import annotations

import os
from typing import Mapping, Optional

_MIN_JWT_SECRET_LEN = 32
# Placeholder values that shipped in backend/.env.example; never valid secrets.
_JWT_PLACEHOLDERS = frozenset({
    "change_this_to_a_random_64_hex_string",
    "change_this_to_a_random_hex_string",
})


def is_production(env: Mapping[str, str] = os.environ) -> bool:
    return env.get("ENVIRONMENT", "development") == "production"


def jwt_secret_problem(secret: Optional[str]) -> Optional[str]:
    """Why `secret` is unusable as a JWT signing key, or None if it is fine."""
    if not secret:
        return "JWT_SECRET is not set"
    if secret in _JWT_PLACEHOLDERS:
        return "JWT_SECRET is the .env.example placeholder"
    if len(secret) < _MIN_JWT_SECRET_LEN:
        return f"JWT_SECRET is shorter than {_MIN_JWT_SECRET_LEN} characters"
    return None


def docs_enabled(env: Mapping[str, str] = os.environ) -> bool:
    """OpenAPI/Swagger are off unless ENABLE_API_DOCS=true."""
    return env.get("ENABLE_API_DOCS", "false").lower() == "true"


def validate_startup_config(env: Mapping[str, str] = os.environ) -> None:
    """Raise RuntimeError listing every unsafe setting when ENVIRONMENT=production.

    Outside production a weak JWT secret is only logged (by database._load_jwt_secret).
    """
    if not is_production(env):
        return
    problems = []
    jwt_problem = jwt_secret_problem(env.get("JWT_SECRET"))
    if jwt_problem:
        problems.append(jwt_problem)
    if "*" in env.get("ALLOWED_ORIGINS", ""):
        problems.append("ALLOWED_ORIGINS must not contain '*' in production")
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))
