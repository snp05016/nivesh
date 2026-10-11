"""DB-06: right to erasure.

DELETE /api/me/account used to record a request that nothing ever executed.
erase_user() now applies ERASURE_POLICY to every users.id foreign key in one
transaction and tombstones the user; process_due_deletion_requests() runs it
for requests past the grace period.
"""
from __future__ import annotations

import functools
from datetime import datetime, timedelta, timezone
from uuid import uuid4

# pyright: reportMissingImports=false

# FINSEC-03: both deletion routes re-authenticate with the account password.
_PASSWORD = "Erase-Me-123"


@functools.cache
def _password_hash() -> str:
    import database

    return database._hash_password(_PASSWORD)


def _new_user() -> int:
    import database
    from models.db_models import User

    with database.get_session() as session:
        user = User(username=f"erase_{uuid4().hex[:12]}", password_hash=_password_hash(), display_name="Erase Me")
        session.add(user)
        session.commit()
        return int(user.id)  # type: ignore[arg-type]


def _request(user_id: int, age_days: float = 0) -> int:
    import database
    from models.db_models import DataDeletionRequest
    from services.compliance_service import request_account_deletion

    request_id = int(request_account_deletion(user_id)["id"])
    if age_days:
        with database.get_session() as session:
            row = session.get(DataDeletionRequest, request_id)
            row.requested_at = datetime.now(timezone.utc) - timedelta(days=age_days)  # type: ignore[union-attr,assignment]
            session.commit()
    return request_id


def _status(request_id: int) -> str:
    import database
    from models.db_models import DataDeletionRequest

    with database.get_session() as session:
        return str(session.get(DataDeletionRequest, request_id).status)  # type: ignore[union-attr]


def test_erasure_policy_covers_every_user_fk():
    from services.compliance_service import ERASURE_POLICY, user_fk_columns

    fks = {f"{t.name}.{c.name}" for t, c in user_fk_columns()}
    assert fks - set(ERASURE_POLICY) == set(), "users.id FKs without an erasure policy"
    assert set(ERASURE_POLICY) - fks == set(), "stale ERASURE_POLICY entries"
    assert set(ERASURE_POLICY.values()) <= {"delete", "nullify", "retain"}


def test_erase_user_end_to_end():
    import database
    from models.db_models import (
        AnalysisHistory, AuditLogEntry, DeviceToken, KYCConsent, Portfolio,
        PortfolioGroup, PriceTarget, Transaction, User, UserBlock,
    )
    from services.compliance_service import erase_user

    uid, other = _new_user(), _new_user()
    with database.get_session() as s:
        group = PortfolioGroup(user_id=uid, name="Core Holdings", is_default=True)
        s.add(group)
        s.flush()
        analysis = AnalysisHistory(user_id=uid, ticker="TCS", analysis_date="2026-10-01", signal="HOLD", full_json="{}")
        s.add_all([
            analysis,
            Portfolio(user_id=uid, ticker="TCS", company_name="TCS", shares=1, buy_price=100,
                      group_name="holdings", group_id=group.id),
            Transaction(user_id=uid, group_id=group.id, ticker="TCS", transaction_type="BUY", quantity=1, price=100),
            PriceTarget(user_id=uid, ticker="TCS", target_price=120, direction="above"),
            DeviceToken(user_id=uid, device_token=f"tok-{uuid4().hex}"),
            KYCConsent(user_id=uid, consent_type="credit_check", granted=True, ip_address="10.0.0.1"),
            AuditLogEntry(user_id=uid, action="test_event", details={}, ip_address="10.0.0.1"),
            UserBlock(blocker_user_id=uid, blocked_user_id=other),
            UserBlock(blocker_user_id=other, blocked_user_id=uid),
        ])
        s.commit()
        analysis_id = analysis.id
    request_id = _request(uid)

    result = erase_user(uid, request_id=request_id)

    assert result["erased"] is True
    with database.get_session() as s:
        for model in (Portfolio, PortfolioGroup, Transaction, PriceTarget, DeviceToken):
            assert s.query(model).filter_by(user_id=uid).count() == 0, model.__tablename__
        assert s.query(UserBlock).filter_by(blocker_user_id=uid).count() == 0
        assert s.query(UserBlock).filter_by(blocker_user_id=other, blocked_user_id=uid).count() == 1
        kept = s.get(AnalysisHistory, analysis_id)
        assert kept is not None and kept.user_id is None  # de-identified, not deleted

        consents = s.query(KYCConsent).filter_by(user_id=uid).all()
        assert len(consents) == 1 and consents[0].ip_address is None
        audit = s.query(AuditLogEntry).filter_by(user_id=uid).all()
        assert {a.action for a in audit} >= {"test_event", "account_deletion_requested", "account_erased"}
        assert all(a.ip_address is None for a in audit)

        user = s.get(User, uid)
        assert user is not None and user.deleted_at is not None
        assert str(user.username).startswith("deleted_")
        assert str(user.display_name) == "Deleted user"
        assert str(user.password_hash) != _password_hash()
        assert s.get(User, other).deleted_at is None  # type: ignore[union-attr]
    assert _status(request_id) == "completed"


def test_process_due_requests_respects_grace():
    from services.compliance_service import process_due_deletion_requests

    fresh_user, due_user = _new_user(), _new_user()
    fresh = _request(fresh_user, age_days=1)
    due = _request(due_user, age_days=8)

    assert process_due_deletion_requests(grace_days=7) >= 1

    assert _status(fresh) == "pending"
    assert _status(due) == "completed"


def test_cancelled_request_not_processed():
    import database
    from models.db_models import User
    from services.compliance_service import cancel_deletion_request, process_due_deletion_requests

    uid = _new_user()
    request_id = _request(uid, age_days=30)
    assert cancel_deletion_request(uid)["cancelled"] is True

    process_due_deletion_requests(grace_days=7)

    assert _status(request_id) == "cancelled"
    with database.get_session() as s:
        assert s.get(User, uid).deleted_at is None  # type: ignore[union-attr]


def test_delete_account_endpoint_reports_schedule(client):
    import database

    uid = _new_user()
    headers = {"Authorization": f"Bearer {database.create_access_token(uid)}"}

    resp = client.request("DELETE", "/api/me/account", json={"password": _PASSWORD}, headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] is True and body["status"] == "pending"
    assert body["scheduled_erasure_after_days"] == 7


def test_deletion_routes_require_password(client):
    import database

    uid = _new_user()
    headers = {"Authorization": f"Bearer {database.create_access_token(uid)}"}

    wrong = {"password": "not-the-password"}
    assert client.post("/api/v1/compliance/deletion-requests", json=wrong, headers=headers).status_code == 403
    assert client.request("DELETE", "/api/me/account", json=wrong, headers=headers).status_code == 403
    assert client.post("/api/v1/compliance/deletion-requests", json={}, headers=headers).status_code == 422
    assert client.get("/api/v1/compliance/deletion-requests/status", headers=headers).json() == {"status": None}


def test_password_guessing_shares_per_user_limit(client):
    # Both re-auth routes draw on one "compliance" bucket (10/hour per user).
    import database

    headers = {"Authorization": f"Bearer {database.create_access_token(_new_user())}"}
    wrong = {"password": "not-the-password"}
    for i in range(10):
        path = "/api/me/account" if i % 2 else "/api/v1/compliance/deletion-requests"
        assert client.request("DELETE" if i % 2 else "POST", path, json=wrong, headers=headers).status_code == 403
    resp = client.request("DELETE", "/api/me/account", json=wrong, headers=headers)
    assert resp.status_code == 429, resp.text


def test_erased_user_token_and_login_rejected(client):
    import database
    from models.db_models import User
    from services.compliance_service import erase_user

    uid = _new_user()
    with database.get_session() as s:
        username = str(s.get(User, uid).username)  # type: ignore[union-attr]
    headers = {"Authorization": f"Bearer {database.create_access_token(uid)}"}
    assert client.get("/api/me/subscription", headers=headers).status_code == 200

    resp = client.post("/api/v1/compliance/deletion-requests", json={"password": _PASSWORD}, headers=headers)
    assert resp.status_code == 200, resp.text
    erase_user(uid, request_id=int(resp.json()["id"]))

    assert database.verify_access_token(headers["Authorization"].split(" ", 1)[1]) is None
    assert client.get("/api/me/subscription", headers=headers).status_code == 401
    assert client.post("/login", json={"username": username, "password": _PASSWORD}).status_code == 401
