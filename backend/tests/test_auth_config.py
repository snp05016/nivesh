"""JWT secret fail-fast and token rejection reasons (SILENT-09)."""
import logging
import re
from datetime import datetime, timedelta, timezone

import pytest


@pytest.mark.parametrize("env", [
    {"ENVIRONMENT": "production"},
    {"ENVIRONMENT": "production", "JWT_SECRET": "change_this_to_a_random_64_hex_string"},
    {"ENVIRONMENT": "production", "JWT_SECRET": "too-short"},
])
def test_load_jwt_secret_refuses_in_production(env):
    import database

    with pytest.raises(RuntimeError):
        database._load_jwt_secret(env)


def test_load_jwt_secret_returns_configured_value():
    import database

    secret = "s" * 48
    assert database._load_jwt_secret({"ENVIRONMENT": "production", "JWT_SECRET": secret}) == secret


def test_load_jwt_secret_dev_warns(caplog):
    import database

    with caplog.at_level(logging.CRITICAL, logger="nivesh.auth"):
        secret = database._load_jwt_secret({"ENVIRONMENT": "development"})

    assert re.fullmatch(r"[0-9a-f]{64}", secret)
    assert any(r.levelno == logging.CRITICAL for r in caplog.records)


def test_verify_expired_token_returns_none_and_logs(caplog):
    import jwt as pyjwt

    import database

    token = pyjwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
        database._JWT_SECRET,
        algorithm="HS256",
    )
    with caplog.at_level(logging.DEBUG, logger="nivesh.auth"):
        assert database.verify_access_token(token) is None

    assert any(r.levelno == logging.DEBUG and "expired" in r.getMessage() for r in caplog.records)


def test_bad_signature_logs_warning(caplog):
    import jwt as pyjwt

    import database

    token = pyjwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "some-other-secret-that-is-long-enough-1234",
        algorithm="HS256",
    )
    with caplog.at_level(logging.DEBUG, logger="nivesh.auth"):
        assert database.verify_access_token(token) is None

    assert any(r.levelno == logging.WARNING and "signature" in r.getMessage() for r in caplog.records)


def test_malformed_token_returns_none():
    import database

    assert database.verify_access_token("not-a-jwt") is None
