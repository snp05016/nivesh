"""CMON-19: login/register limits must key on the real route paths."""
import pytest
from fastapi import HTTPException

from core.rate_limiter import _check_rate_limit


def test_sixth_login_in_a_minute_is_429(client):
    creds = {"username": "_rl_nobody_cmon19", "password": "wrong-password"}
    for _ in range(5):
        assert client.post("/login", json=creds).status_code == 401
    resp = client.post("/login", json=creds)
    assert resp.status_code == 429
    assert "retry-after" in {k.lower() for k in resp.headers}


def test_register_limit_key_matches():
    for _ in range(10):
        assert _check_rate_limit("reg_cmon19", "/register") is True
    with pytest.raises(HTTPException) as exc:
        _check_rate_limit("reg_cmon19", "/register")
    assert exc.value.status_code == 429
