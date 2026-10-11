"""FINSEC-23: per-user limits on identity/money write endpoints, shared via Redis.

Under pytest core.rate_limiter._redis() returns None, so counts use the in-process
store, which the conftest _reset_rate_limiter fixture clears around every test.
"""
from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from core import rate_limiter

_CONSENT = {"consent_type": "data_sharing", "granted": True}


def _new_user_headers() -> dict:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"rl_{uuid4().hex[:12]}", password_hash="x", display_name="RL Test")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    return {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


def test_kyc_consent_write_limited(client):
    headers = _new_user_headers()
    for _ in range(30):
        resp = client.post("/api/kyc/consents", json=_CONSENT, headers=headers)
        assert resp.status_code == 200, resp.text
    resp = client.post("/api/kyc/consents", json=_CONSENT, headers=headers)
    assert resp.status_code == 429, resp.text
    assert int(resp.headers["Retry-After"]) > 0


def test_limit_is_per_user(client):
    first, second = _new_user_headers(), _new_user_headers()
    for _ in range(30):
        assert client.post("/api/kyc/consents", json=_CONSENT, headers=first).status_code == 200
    assert client.post("/api/kyc/consents", json=_CONSENT, headers=first).status_code == 429
    assert client.post("/api/kyc/consents", json=_CONSENT, headers=second).status_code == 200


def test_redis_disabled_under_pytest():
    assert rate_limiter._redis() is None


def _redis_stub(count: int | None = None, error: Exception | None = None) -> MagicMock:
    pipe = MagicMock()
    if error is not None:
        pipe.execute.side_effect = error
    else:
        pipe.execute.return_value = [count, True]
    r = MagicMock()
    r.pipeline.return_value = pipe
    return r


def test_hit_uses_redis_when_available(monkeypatch):
    monkeypatch.setattr(rate_limiter, "_redis", lambda: _redis_stub(count=30))
    assert rate_limiter._check_rate_limit("user:1", "kyc_consent") is True
    assert len(rate_limiter._rate_limit_store) == 0  # counted in Redis, not memory

    monkeypatch.setattr(rate_limiter, "_redis", lambda: _redis_stub(count=31))
    with pytest.raises(HTTPException) as exc:
        rate_limiter._check_rate_limit("user:1", "kyc_consent")
    assert exc.value.status_code == 429
    assert exc.value.headers is not None and int(exc.value.headers["Retry-After"]) > 0


def test_redis_error_falls_back_to_memory(monkeypatch):
    monkeypatch.setattr(rate_limiter, "_redis_down_until", 0.0)
    monkeypatch.setattr(rate_limiter, "_redis", lambda: _redis_stub(error=ConnectionError("down")))
    assert rate_limiter._check_rate_limit("user:1", "kyc_consent") is True
    assert len(rate_limiter._rate_limit_store["user:1"]["kyc_consent"]) == 1
    assert rate_limiter._redis_down_until > 0  # breaker opened
