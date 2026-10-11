"""Fail-closed production startup configuration (REL-26)."""
import pytest

from core import config_guard

_STRONG = "a" * 64


@pytest.mark.parametrize("secret", ["", "short", *sorted(config_guard._JWT_PLACEHOLDERS)])
def test_prod_requires_strong_jwt(secret):
    with pytest.raises(RuntimeError):
        config_guard.validate_startup_config({"ENVIRONMENT": "production", "JWT_SECRET": secret})


def test_prod_missing_jwt_raises():
    with pytest.raises(RuntimeError):
        config_guard.validate_startup_config({"ENVIRONMENT": "production"})


def test_prod_refuses_wildcard_cors():
    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS"):
        config_guard.validate_startup_config({
            "ENVIRONMENT": "production", "JWT_SECRET": "x" * 40, "ALLOWED_ORIGINS": "*",
        })


def test_prod_valid_passes():
    config_guard.validate_startup_config({
        "ENVIRONMENT": "production", "JWT_SECRET": _STRONG,
        "ALLOWED_ORIGINS": "https://app.example",
    })


def test_dev_does_not_raise():
    config_guard.validate_startup_config({"ENVIRONMENT": "development"})
    config_guard.validate_startup_config({})


def test_docs_disabled_by_default():
    assert config_guard.docs_enabled({}) is False
    assert config_guard.docs_enabled({"ENABLE_API_DOCS": "true"}) is True


def test_cors_preflight_random_origin_no_acao(client):
    resp = client.options("/ping", headers={
        "Origin": "https://evil.example",
        "Access-Control-Request-Method": "GET",
    })
    assert "access-control-allow-origin" not in resp.headers


def test_shutdown_reaps_workers_when_scheduler_stop_fails(monkeypatch):
    import asyncio

    import main
    from services import job_manager

    called = []

    def broken_stop():
        raise RuntimeError("scheduler already gone")

    monkeypatch.setattr(main, "stop_scheduler", broken_stop)
    monkeypatch.setattr(job_manager, "shutdown_all", lambda: called.append(True))

    asyncio.run(main._on_shutdown())

    assert called == [True]
