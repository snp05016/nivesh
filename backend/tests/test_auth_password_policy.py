"""Password policy on POST /register (UX-14): 8..72 bytes (bcrypt limit), 400 with a plain-text detail."""

from __future__ import annotations

from uuid import uuid4

import pytest
from tests.conftest import REGISTER_CONSENT


@pytest.fixture
def register(client, monkeypatch):
    import routers.auth as auth_router

    monkeypatch.setattr(auth_router, "_check_rate_limit", lambda *_args, **_kwargs: True)

    def _post(password: str):
        return client.post(
            "/register",
            json={
                "username": f"pwpolicy_{uuid4().hex[:12]}",
                "password": password,
                "display_name": "Password Policy",
                **REGISTER_CONSENT,
            },
        )

    return _post


def test_register_rejects_short_password(register):
    response = register("1234567")

    assert response.status_code == 400
    assert "8 characters" in response.json()["detail"]


def test_register_accepts_8_char_password(register):
    response = register("abcd1234")

    assert response.status_code == 200, response.text
    assert response.json()["username"].startswith("pwpolicy_")


def test_register_accepts_72_byte_password(register):
    response = register("a" * 72)

    assert response.status_code == 200, response.text


@pytest.mark.parametrize("password", ["a" * 73, "a" * 129, "\u20b9" * 25])
def test_register_rejects_overlong_password(register, password):
    # "\u20b9" (rupee sign) is 3 UTF-8 bytes: 25 of them = 75 bytes > 72.
    response = register(password)

    assert response.status_code == 400
    assert "72 characters" in response.json()["detail"]
