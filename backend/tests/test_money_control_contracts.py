"""TEST-10: contract and isolation coverage for the money-control and account surface.

Complements the route tests in test_fixed_deposits_api.py, test_finance_loans.py
and test_subscription_compliance_api.py (auth 401s, KYC fail-closed, amount
bounds, deletion round trip) with what they leave out: response keys against the
Swift DTOs, consent revocation, the entitlement lifecycle through a real gated
route, /api/me idempotency, and cross-user isolation with a second real login.

Every DB write goes through database.get_session() into the per-session temp DB
(backend/conftest.py); nothing here calls the network or an LLM.
"""
from __future__ import annotations

import functools
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

import config.settings

IOS_MODELS = Path(__file__).resolve().parents[2] / "ios" / "StockApp" / "stockme" / "stockme" / "Models"
GATED_ROUTE = "/fundamentals/TCS/risk-signals"  # gated on swot_analysis (pro)


def _swift_keys(file_name: str, struct: str) -> set[str]:
    """JSON keys of a Swift DTO: the raw values of its CodingKeys enum."""
    path = IOS_MODELS / file_name
    if not path.is_file():  # backend-only checkout (the server) has no iOS tree
        pytest.skip("iOS sources not present")
    body = path.read_text(encoding="utf-8").split(f"struct {struct}:", 1)[1]
    enum = body.split("enum CodingKeys", 1)[1].split("}", 1)[0]
    keys = set()
    for line in enum.splitlines():
        line = line.strip()
        if line.startswith("case "):
            for item in line[len("case "):].split(","):
                name, _, raw = item.partition("=")
                keys.add(raw.strip().strip('"') if raw else name.strip())
    return keys


# FINSEC-03: deletion routes re-authenticate with the account password.
_PASSWORD = "Delete-Me-123"


@functools.cache
def _password_hash() -> str:
    import database

    return database._hash_password(_PASSWORD)


def _new_user() -> tuple[int, dict]:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"mc_{uuid4().hex[:12]}", password_hash=_password_hash(), display_name="Money Control Test")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    return user_id, {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


@pytest.fixture(scope="module")
def other_user(client) -> dict:
    """A second user with a JWT from the real /register + /login flow (never an admin bypass)."""
    creds = {"username": "test_mc_other_9998", "password": "McOther!9998x"}
    client.post("/register", json={**creds, "display_name": "MC Other 9998"})  # may already exist
    resp = client.post("/login", json=creds)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return {"id": data["user_id"], "headers": {"Authorization": f"Bearer {data['access_token']}"}}


@pytest.fixture
def demo_mode(monkeypatch):
    """Loans and FD bookings answer 404 unless DEMO_MODE is on (FAKE-23)."""
    monkeypatch.setattr(config.settings, "DEMO_MODE", True)


@pytest.fixture
def fd_scheme(demo_mode):
    """A 7.00% scheme: 10,000 to 10,00,000, 6 to 60 months; removed (with its bookings) afterwards."""
    import database
    from models.db_models import FixedDepositScheme  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        scheme = FixedDepositScheme(
            issuer_name=f"MC Bank {uuid4().hex[:8]}",
            min_tenure_months=6,
            max_tenure_months=60,
            min_amount=10_000,
            max_amount=10_00_000,
            interest_rate_pct=7.0,
            senior_citizen_bonus_pct=0.5,
            is_active=True,
        )
        session.add(scheme)
        session.commit()
        scheme_id = int(scheme.id)  # type: ignore[arg-type]
    yield scheme_id
    with database.get_session() as session:
        row = session.get(FixedDepositScheme, scheme_id)
        if row is not None:
            session.delete(row)  # ORM cascade removes this scheme's bookings
            session.commit()


@pytest.fixture
def loan_offer(demo_mode):
    """An active personal-loan offer: 50,000 to 5,00,000, 6 to 60 months."""
    import database
    from models.db_models import LoanOffer  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        offer = LoanOffer(
            nbfc_name=f"MC NBFC {uuid4().hex[:8]}",
            loan_type="personal",
            min_amount=50_000,
            max_amount=5_00_000,
            interest_rate_pct=12.0,
            min_tenure_months=6,
            max_tenure_months=60,
            min_credit_score=600,
            processing_fee_pct=1.0,
            is_active=True,
        )
        session.add(offer)
        session.commit()
        offer_id = int(offer.id)  # type: ignore[arg-type]
    yield offer_id
    with database.get_session() as session:
        row = session.get(LoanOffer, offer_id)
        if row is not None:
            session.delete(row)  # ORM cascade removes this offer's applications
            session.commit()


def _book_fd(client, headers, scheme_id, device_id):
    return client.post(
        "/api/fixed-deposits/bookings",
        json={
            "scheme_id": scheme_id,
            "principal_amount": 1_00_000,
            "tenure_months": 12,
            "payment_method": "upi",
            "device_id": device_id,
        },
        headers=headers,
    )


def _grant_sim_binding(client, headers, device_id):
    consent = client.post("/api/kyc/consents", json={"consent_type": "sim_binding", "granted": True}, headers=headers)
    assert consent.status_code == 200, consent.text
    binding = client.post("/api/kyc/device-binding", json={"device_id": device_id}, headers=headers)
    assert binding.status_code == 200, binding.text
    verify = client.get("/api/kyc/device-binding/verify", params={"device_id": device_id}, headers=headers)
    assert verify.status_code == 200, verify.text
    assert verify.json()["verified"] is True


# ---------------------------------------------------------------------------
# Fixed deposits: KYC gate + Swift contract
# ---------------------------------------------------------------------------

def test_fd_booking_kyc_gate_and_swift_contract(client, fd_scheme, other_user):
    _, headers = _new_user()
    device_id = f"mc-dev-{uuid4().hex}"

    before = _book_fd(client, headers, fd_scheme, device_id)
    assert before.status_code == 200, before.text
    assert before.json()["status"] != "confirmed"

    _grant_sim_binding(client, headers, device_id)
    resp = _book_fd(client, headers, fd_scheme, device_id)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "confirmed"
    assert _swift_keys("FixedDepositModels.swift", "FDBookingResponse") <= set(body)

    others = client.get("/api/fixed-deposits/bookings", headers=other_user["headers"])
    assert others.status_code == 200, others.text
    assert body["id"] not in {b["id"] for b in others.json()}


def test_consent_revoke_blocks_booking(client, fd_scheme):
    _, headers = _new_user()
    device_id = f"mc-dev-{uuid4().hex}"
    _grant_sim_binding(client, headers, device_id)
    assert _book_fd(client, headers, fd_scheme, device_id).json()["status"] == "confirmed"

    revoked = client.delete("/api/kyc/consents/sim_binding", headers=headers)
    assert revoked.status_code == 200, revoked.text

    resp = _book_fd(client, headers, fd_scheme, device_id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] != "confirmed"


# ---------------------------------------------------------------------------
# Entitlements through a real gated route: free -> pro -> cancelled -> lapsed
# ---------------------------------------------------------------------------

def test_entitlement_lifecycle_on_gated_route(client):
    from database import get_session
    from models.db_models import UserSubscription  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)
    from services import subscription_service

    user_id, headers = _new_user()

    ent = client.get("/api/v1/subscription/entitlements", headers=headers).json()
    assert ent["tier"] == "free" and ent["features"]["swot_analysis"] is False
    assert client.get(GATED_ROUTE, headers=headers).status_code == 402

    # Service call, not POST /upgrade: the mock purchase route is being put behind
    # an environment switch (#666), and this test is about the gate, not the purchase.
    subscription_service.mock_upgrade(user_id, "pro", "monthly")
    assert client.get(GATED_ROUTE, headers=headers).status_code == 200

    cancelled = client.post("/api/v1/subscription/cancel", headers=headers)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["is_active"] is False
    assert client.get(GATED_ROUTE, headers=headers).status_code == 200  # paid period still running

    with get_session() as session:
        session.query(UserSubscription).filter(UserSubscription.user_id == user_id).update(
            {"renews_at": datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)}
        )
        session.commit()

    lapsed = client.get(GATED_ROUTE, headers=headers)
    assert lapsed.status_code == 402, lapsed.text
    assert lapsed.json()["detail"]["current_tier"] == "free"


# ---------------------------------------------------------------------------
# Subscription contract keys
# ---------------------------------------------------------------------------

def test_subscription_routes_match_swift_dto(client):
    _, headers = _new_user()
    v1 = client.get("/api/v1/subscription", headers=headers)
    me = client.get("/api/me/subscription", headers=headers)
    assert v1.status_code == 200 and me.status_code == 200, (v1.text, me.text)
    assert v1.json() == me.json()
    assert set(v1.json()) == _swift_keys("SubscriptionModels.swift", "CurrentSubscriptionDTO")


def test_entitlements_keys_match_swift_dto(client):
    _, headers = _new_user()
    resp = client.get("/api/v1/subscription/entitlements", headers=headers)
    assert resp.status_code == 200, resp.text
    # EntitlementsDTO (DisclosureModels.swift) has no CodingKeys: its property names are the keys.
    assert set(resp.json()) == {"tier", "features", "catalog"}


# ---------------------------------------------------------------------------
# /api/me/account and compliance isolation
# ---------------------------------------------------------------------------

def test_delete_my_account_is_idempotent(client):
    from database import get_session
    from models.db_models import DataDeletionRequest  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    user_id, headers = _new_user()
    first = client.request("DELETE", "/api/me/account", json={"password": _PASSWORD}, headers=headers)
    second = client.request("DELETE", "/api/me/account", json={"password": _PASSWORD}, headers=headers)

    assert first.status_code == 200 and second.status_code == 200, (first.text, second.text)
    assert first.json()["created"] is True
    assert second.json()["created"] is False
    assert second.json()["id"] == first.json()["id"]
    status = client.get("/api/v1/compliance/deletion-requests/status", headers=headers)
    assert status.json()["status"] == "pending"
    with get_session() as session:
        assert session.query(DataDeletionRequest).filter(DataDeletionRequest.user_id == user_id).count() == 1


def test_audit_trail_is_per_user(client, other_user):
    user_id, headers = _new_user()
    created = client.post(
        "/api/v1/compliance/deletion-requests", json={"reason": "test", "password": _PASSWORD}, headers=headers
    )
    assert created.status_code == 200, created.text
    assert client.post("/api/v1/compliance/deletion-requests/cancel", headers=headers).status_code == 200

    own = client.get("/api/v1/compliance/audit-trail", headers=headers).json()
    assert own and {e["user_id"] for e in own} == {user_id}

    trail = client.get("/api/v1/compliance/audit-trail", headers=other_user["headers"])
    assert trail.status_code == 200, trail.text
    assert all(e["user_id"] == other_user["id"] for e in trail.json())


# ---------------------------------------------------------------------------
# Finance: loan applications are owner-only
# ---------------------------------------------------------------------------

def test_loan_application_not_readable_by_other_user(client, loan_offer, other_user):
    _, headers = _new_user()
    created = client.post(
        "/api/finance/loan-applications",
        json={"loan_offer_id": loan_offer, "requested_amount": 1_00_000, "requested_tenure_months": 24},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    app_id = created.json()["id"]

    assert client.get(f"/api/finance/loan-applications/{app_id}", headers=headers).status_code == 200
    other = client.get(f"/api/finance/loan-applications/{app_id}", headers=other_user["headers"])
    assert other.status_code in (403, 404), other.text
    listed = client.get("/api/finance/loan-applications", headers=other_user["headers"]).json()
    assert app_id not in {a["id"] for a in listed}
