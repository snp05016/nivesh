"""Fail-closed startup configuration checks (REL-26, SILENT-09, OPS-13).

Production must never boot with a forgeable JWT secret or credentialed wildcard CORS.
Only an explicit ENVIRONMENT=development/test is non-production: unset or misspelled
counts as production, so a missing variable can only make the server stricter.
"""
from __future__ import annotations

import logging
import os
from typing import Mapping, Optional

logger = logging.getLogger("nivesh.config")

_NON_PRODUCTION = ("development", "test")
_APNS_KEYS = ("APNS_AUTH_KEY_PATH", "APNS_KEY_ID", "APNS_TEAM_ID")

_MIN_JWT_SECRET_LEN = 32
# Placeholder values that shipped in backend/.env.example; never valid secrets.
_JWT_PLACEHOLDERS = frozenset({
    "change_this_to_a_random_64_hex_string",
    "change_this_to_a_random_hex_string",
})


def is_production(env: Mapping[str, str] = os.environ) -> bool:
    return env.get("ENVIRONMENT") not in _NON_PRODUCTION


def apns_configured(env: Mapping[str, str] = os.environ) -> bool:
    return all(env.get(k) for k in _APNS_KEYS)


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
    """Raise RuntimeError listing every unsafe setting in production (ENVIRONMENT unset counts).

    Outside production a weak JWT secret is only logged (by database._load_jwt_secret).
    Missing APNs credentials are logged CRITICAL, not fatal: alerts can be switched
    off on purpose with ALERTS_PUSH_DISABLED=true.
    """
    environment = env.get("ENVIRONMENT")
    if environment is None:
        logger.warning("ENVIRONMENT is unset - treating as production")
    if not is_production(env):
        return
    problems = []
    if environment not in (None, "production"):
        problems.append(f"ENVIRONMENT={environment!r} is not one of development, test, production")
    jwt_problem = jwt_secret_problem(env.get("JWT_SECRET"))
    if jwt_problem:
        problems.append(jwt_problem)
    if "*" in env.get("ALLOWED_ORIGINS", ""):
        problems.append("ALLOWED_ORIGINS must not contain '*' in production")
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))
    if not apns_configured(env):
        if env.get("ALERTS_PUSH_DISABLED", "false").lower() != "true":
            logger.critical(
                "APNs not configured (%s) - price-alert pushes cannot be delivered; "
                "set them or ALERTS_PUSH_DISABLED=true", ", ".join(_APNS_KEYS),
            )
    elif env.get("APNS_ENVIRONMENT") != "production":
        logger.critical("APNS_ENVIRONMENT is not 'production' - pushes go to the APNs sandbox")
