"""Focused FastAPI contract tests for offline backend behavior."""

from __future__ import annotations

from uuid import uuid4
from tests.conftest import REGISTER_CONSENT


def _unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _create_contract_user() -> tuple[int, str]:
    import database
    from models.db_models import User

    username = _unique_name("contract_user")
    with database.get_session() as session:
        user = User(username=username, password_hash="test", display_name="Contract User")
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id, database.create_access_token(user.id)


def test_ping_contract_is_zero_dependency(client):
    response = client.get("/ping")

    assert response.status_code == 200
    assert response.json() == {"pong": True}


def test_register_duplicate_username_returns_400(client, monkeypatch):
    import routers.auth as auth_router

    monkeypatch.setattr(auth_router, "_check_rate_limit", lambda *_args, **_kwargs: True)
    username = _unique_name("contract_register")
    payload = {
        "username": username,
        "password": "ContractPass!123",
        "display_name": "Contract Register",
        **REGISTER_CONSENT,
    }

    first = client.post("/register", json=payload)
    duplicate = client.post("/register", json=payload)

    assert first.status_code == 200
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == "Username already exists"


def test_register_returns_usable_access_token(client, monkeypatch):
    # iOS decodes the /register response into LoggedInUser, which requires access_token (CMON-01).
    import database
    import routers.auth as auth_router

    monkeypatch.setattr(auth_router, "_check_rate_limit", lambda *_args, **_kwargs: True)
    username = _unique_name("contract_signup")

    response = client.post(
        "/register",
        json={
            "username": username,
            "password": "ContractPass!123",
            "display_name": "Contract Signup",
            **REGISTER_CONSENT,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == username
    assert body["display_name"] == "Contract Signup"
    assert body["token_type"] == "bearer"
    assert database.verify_access_token(body["access_token"]) == body["user_id"]

    authed = client.get(
        "/api/kyc/consents",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert authed.status_code == 200


def test_login_rejects_invalid_credentials_without_token(client):
    response = client.post(
        "/login",
        json={"username": _unique_name("missing"), "password": "wrong"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["detail"] == "Invalid username or password"
    assert "access_token" not in body


def test_analyze_valid_request_returns_async_job_contract(client, monkeypatch):
    import database
    import services.job_manager as job_manager

    user_id, _token = _create_contract_user()
    monkeypatch.setattr(job_manager, "spawn_job", lambda *args, **kwargs: None)
    # Force a cache miss: scan_type is validated now, so a random one no longer dodges the cache.
    monkeypatch.setattr(database, "get_analysis_for_date", lambda *args, **kwargs: None)

    response = client.post(
        "/analyze",
        json={
            "ticker": "RELIANCE",
            "exchange": "NSE",
            "user_id": user_id,
            "scan_type": "standard",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert set(body) == {"job_id", "status", "ticker", "scan_type"}
    assert len(body["job_id"]) == 36
    assert body["status"] == "QUEUED"
    assert body["ticker"] == "RELIANCE"

    database.update_job(body["job_id"], status="CANCELLED")


def test_analyze_rejects_unknown_scan_type(client):
    # An unknown scan_type used to bypass the cache and the per-type job guard (AUTH-17).
    user_id, _token = _create_contract_user()

    response = client.post(
        "/analyze",
        json={"ticker": "RELIANCE", "exchange": "NSE", "user_id": user_id, "scan_type": "standard2"},
    )

    assert response.status_code == 422
    assert "scan_type must be standard, deep or extreme" in response.text


def test_analyze_rejects_invalid_exchange_before_job_creation(client):
    user_id, _token = _create_contract_user()

    response = client.post(
        "/analyze",
        json={"ticker": "RELIANCE", "exchange": "NASDAQ", "user_id": user_id},
    )

    assert response.status_code == 422
    assert "Exchange must be NSE or BSE" in response.text


def test_watchlist_add_accepts_documented_zero_value_sentinel(client):
    user_id, token = _create_contract_user()

    response = client.post(
        "/watchlist/add",
        json={
            "user_id": user_id,
            "ticker": "INFY",
            "exchange": "NSE",
            "company_name": "Infosys Ltd",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "ticker": "INFY"}
