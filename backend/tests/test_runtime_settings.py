"""Fail-closed ENVIRONMENT handling and production config checks (OPS-13)."""
import logging

import pytest

from core import config_guard

_STRONG = "a" * 64
_APNS = {"APNS_AUTH_KEY_PATH": "/k.p8", "APNS_KEY_ID": "KEY", "APNS_TEAM_ID": "TEAM"}
_LOGGER = "nivesh.config"


@pytest.mark.parametrize("env", [{}, {"ENVIRONMENT": "production"}, {"ENVIRONMENT": "prod"},
                                 {"ENVIRONMENT": "Production"}, {"ENVIRONMENT": ""}])
def test_unset_or_unknown_environment_is_production(env):
    assert config_guard.is_production(env) is True


@pytest.mark.parametrize("value", ["development", "test"])
def test_only_explicit_dev_or_test_is_non_production(value):
    assert config_guard.is_production({"ENVIRONMENT": value}) is False


def test_unset_environment_without_jwt_raises(caplog):
    caplog.set_level(logging.WARNING, logger=_LOGGER)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        config_guard.validate_startup_config({})
    assert "ENVIRONMENT is unset" in caplog.text


@pytest.mark.parametrize("secret", ["", "change_this_to_a_random_64_hex_string"])
def test_prod_weak_jwt_raises(secret):
    with pytest.raises(RuntimeError):
        config_guard.validate_startup_config({"ENVIRONMENT": "production", "JWT_SECRET": secret})


def test_misspelled_environment_raises():
    with pytest.raises(RuntimeError, match="ENVIRONMENT='prod'"):
        config_guard.validate_startup_config({"ENVIRONMENT": "prod", "JWT_SECRET": _STRONG, **_APNS})


def test_docs_default_off():
    assert config_guard.docs_enabled({}) is False
    assert config_guard.docs_enabled({"ENVIRONMENT": "production"}) is False


def test_prod_missing_apns_logs_critical_not_raise(caplog):
    caplog.set_level(logging.WARNING, logger=_LOGGER)
    config_guard.validate_startup_config({"ENVIRONMENT": "production", "JWT_SECRET": _STRONG})
    assert any(r.levelno == logging.CRITICAL and "APNs not configured" in r.getMessage()
               for r in caplog.records)


def test_prod_alerts_push_disabled_silences_apns_check(caplog):
    caplog.set_level(logging.WARNING, logger=_LOGGER)
    config_guard.validate_startup_config({
        "ENVIRONMENT": "production", "JWT_SECRET": _STRONG, "ALERTS_PUSH_DISABLED": "true",
    })
    assert not [r for r in caplog.records if r.levelno == logging.CRITICAL]


def test_prod_apns_sandbox_logs_critical(caplog):
    caplog.set_level(logging.WARNING, logger=_LOGGER)
    base = {"ENVIRONMENT": "production", "JWT_SECRET": _STRONG, **_APNS}
    config_guard.validate_startup_config(base)
    assert any("APNS_ENVIRONMENT" in r.getMessage() for r in caplog.records)

    caplog.clear()
    config_guard.validate_startup_config({**base, "APNS_ENVIRONMENT": "production"})
    assert not [r for r in caplog.records if r.levelno == logging.CRITICAL]


def test_dev_skips_production_checks(caplog):
    caplog.set_level(logging.WARNING, logger=_LOGGER)
    config_guard.validate_startup_config({"ENVIRONMENT": "development"})
    assert not caplog.records


def test_mock_push_forbidden_when_environment_unset(monkeypatch):
    from services.notifications_service import dispatch_mock_push

    monkeypatch.delenv("ENVIRONMENT", raising=False)
    with pytest.raises(PermissionError):
        dispatch_mock_push("abcdef123456", "t", "b", 1)
