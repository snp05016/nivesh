"""AUTH-23: username rules and one normalisation, legacy-hash upgrade, equal bcrypt
work for unknown users, and a per-account login limit."""
from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest

from tests.conftest import REGISTER_CONSENT

PASSWORD = "CredTest!1234"


def _name() -> str:
    return f"cred_{uuid4().hex[:10]}"


def _register(client, username: str):
    return client.post("/register", json={
        "username": username, "password": PASSWORD, "display_name": "Cred Test", **REGISTER_CONSENT,
    })


def test_username_is_normalised_on_register_and_login(client):
    name = _name()
    resp = _register(client, f"  {name.upper()}  ")
    assert resp.status_code == 200, resp.text
    assert resp.json()["username"] == name

    login = client.post("/login", json={"username": f" {name.upper()} ", "password": PASSWORD})
    assert login.status_code == 200, login.text

    dup = _register(client, name)
    assert dup.status_code == 400
    assert dup.json()["detail"] == "Username already exists"


@pytest.mark.parametrize("username", ["", "ab", "a b", "x" * 33, "<script>", "bob@example"])
def test_register_rejects_invalid_username(client, username):
    assert _register(client, username).status_code == 422


def test_legacy_sha256_hash_is_upgraded_on_login(client):
    from database import get_session
    from models.db_models import User

    name = _name()
    with get_session() as session:
        session.add(User(username=name, display_name="Legacy",
                         password_hash=hashlib.sha256(PASSWORD.encode()).hexdigest()))
        session.commit()

    resp = client.post("/login", json={"username": name, "password": PASSWORD})
    assert resp.status_code == 200, resp.text

    with get_session() as session:
        stored = session.query(User.password_hash).filter_by(username=name).scalar()
    assert stored.startswith("$2")
    assert client.post("/login", json={"username": name, "password": PASSWORD}).status_code == 200


@pytest.mark.parametrize("known", [True, False])
def test_login_runs_one_bcrypt_check_for_known_and_unknown_users(client, monkeypatch, known):
    import database

    name = _name()
    if known:
        assert _register(client, name).status_code == 200
    database._dummy_hash()  # build the cached dummy hash outside the counted call

    calls = []
    real_checkpw = database.bcrypt.checkpw

    def counting_checkpw(*args):
        calls.append(1)
        return real_checkpw(*args)

    monkeypatch.setattr(database.bcrypt, "checkpw", counting_checkpw)
    resp = client.post("/login", json={"username": name, "password": "wrong-password"})
    assert resp.status_code == 401
    assert len(calls) == 1


def test_sixth_login_for_one_account_is_429_even_across_ips(client, monkeypatch):
    from core import rate_limiter

    # Lift the per-IP middleware limit (as if each attempt came from a new IP);
    # routers.auth keeps its own reference to the real limiter.
    monkeypatch.setattr(rate_limiter, "_check_rate_limit", lambda *_a, **_k: True)
    creds = {"username": _name(), "password": "wrong-password"}
    for _ in range(5):
        assert client.post("/login", json=creds).status_code == 401
    resp = client.post("/login", json=creds)
    assert resp.status_code == 429
