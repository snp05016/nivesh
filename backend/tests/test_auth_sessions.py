"""AUTH-13: tokens are revocable through users.token_version.

POST /api/v1/auth/logout and /api/v1/auth/change-password bump the version, so
every token issued before stops passing require_auth; a token for a user that
does not exist is rejected too.
"""
from uuid import uuid4

from tests.conftest import REGISTER_CONSENT

_PROBE = "/api/v1/subscription"  # any require_auth route
_PASSWORD = "SessionPass!123"


def _register(client) -> tuple[str, dict]:
    username = f"sess_{uuid4().hex[:10]}"
    resp = client.post("/register", json={
        "username": username, "password": _PASSWORD, "display_name": "Session Test", **REGISTER_CONSENT,
    })
    assert resp.status_code == 200, resp.text
    return username, {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _login(client, username: str, password: str):
    return client.post("/login", json={"username": username, "password": password})


def test_logout_revokes_existing_tokens(client):
    import database
    from models.db_models import DeviceToken  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    username, headers = _register(client)
    assert client.get(_PROBE, headers=headers).status_code == 200
    uid = database.verify_access_token(headers["Authorization"].split(" ", 1)[1])
    with database.get_session() as session:
        session.add(DeviceToken(user_id=uid, device_token=f"tok_{uuid4().hex}", platform="ios"))
        session.commit()

    assert client.post("/api/v1/auth/logout").status_code == 401
    resp = client.post("/api/v1/auth/logout", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "logged_out"}
    assert client.get(_PROBE, headers=headers).status_code == 401
    with database.get_session() as session:  # signed-out devices stop getting pushes
        assert session.query(DeviceToken).filter(DeviceToken.user_id == uid).count() == 0

    fresh = _login(client, username, _PASSWORD)
    assert fresh.status_code == 200, fresh.text
    new_headers = {"Authorization": f"Bearer {fresh.json()['access_token']}"}
    assert client.get(_PROBE, headers=new_headers).status_code == 200


def test_change_password_revokes_tokens_and_swaps_password(client):
    username, headers = _register(client)
    url = "/api/v1/auth/change-password"
    new_password = "AnotherPass!456"

    wrong = client.post(url, json={"current_password": "not-it-at-all", "new_password": new_password}, headers=headers)
    assert wrong.status_code == 400  # not 401: the session itself is still valid
    assert wrong.json()["detail"] == "Current password is incorrect"
    assert client.get(_PROBE, headers=headers).status_code == 200  # a failed attempt revokes nothing

    short = client.post(url, json={"current_password": _PASSWORD, "new_password": "short"}, headers=headers)
    assert short.status_code == 400

    ok = client.post(url, json={"current_password": _PASSWORD, "new_password": new_password}, headers=headers)
    assert ok.status_code == 200, ok.text
    assert ok.json() == {"status": "password_changed"}
    assert client.get(_PROBE, headers=headers).status_code == 401

    assert _login(client, username, _PASSWORD).status_code == 401
    assert _login(client, username, new_password).status_code == 200


def test_token_for_unknown_user_is_rejected(client):
    import database

    token = database.create_access_token(2_000_000_000)
    assert client.get(_PROBE, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_without_ver_claim_still_valid_for_unbumped_user(client):
    """Tokens issued before the "ver" claim existed count as version 0, so the deploy logs nobody out."""
    from datetime import datetime, timedelta, timezone

    import jwt as pyjwt

    import database

    _, headers = _register(client)
    uid = database.verify_access_token(headers["Authorization"].split(" ", 1)[1])
    assert uid is not None
    legacy = pyjwt.encode(
        {"sub": str(uid), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        database._JWT_SECRET,
        algorithm="HS256",
    )
    assert database.verify_access_token(legacy) == uid
