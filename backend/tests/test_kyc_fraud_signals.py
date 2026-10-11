"""FINSEC-17: get_fraud_signals_for_user compared naive attempted_at values
with an aware cutoff in Python, raising TypeError once any bind attempt existed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import config.settings
import database
from models.db_models import DeviceBinding, DeviceBindingAttempt  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)


def _clear(user_id: int) -> None:
    with database.get_session() as session:
        session.query(DeviceBindingAttempt).filter(DeviceBindingAttempt.user_id == user_id).delete()
        session.query(DeviceBinding).filter(DeviceBinding.user_id == user_id).delete()
        session.commit()


@pytest.fixture
def uid(test_user_id):
    _clear(test_user_id)
    yield test_user_id
    _clear(test_user_id)


def test_fraud_signals_after_bind_does_not_raise(uid):
    from services.kyc_consent_service import bind_device, get_fraud_signals_for_user

    bind_device(uid, "dev-fs-1")

    signals = get_fraud_signals_for_user(uid)

    assert signals["total_bind_attempts_24h"] == 1
    assert signals["is_flagged"] is False


def test_old_attempt_excluded_from_24h(uid):
    from services.kyc_consent_service import get_fraud_signals_for_user

    old = datetime.now(timezone.utc) - timedelta(hours=48)
    with database.get_session() as session:
        session.add(DeviceBindingAttempt(
            user_id=uid, device_id="dev-fs-old", attempted_at=old,
            outcome="rejected_rate_limit", reason="test",
        ))
        session.commit()

    signals = get_fraud_signals_for_user(uid)

    assert signals["total_bind_attempts_24h"] == 0
    assert signals["rate_limit_hits_24h"] == 0
    assert signals["is_flagged"] is True


def test_fraud_signals_route_200(client, auth_headers, uid, monkeypatch):
    from services.kyc_consent_service import bind_device

    monkeypatch.setattr(config.settings, "DEMO_MODE", True)  # route is demo-gated

    bind_device(uid, "dev-fs-2")

    resp = client.get("/api/kyc/fraud-signals", headers=auth_headers)

    assert resp.status_code == 200, resp.text
    assert {
        "total_bind_attempts_24h", "cross_user_rejections_total", "rate_limit_hits_24h", "is_flagged",
    } <= resp.json().keys()
