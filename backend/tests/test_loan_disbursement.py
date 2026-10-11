"""GH-670: loan disbursement is idempotent.

- No primary bank account: rejected, nothing persisted (no pile of failed rows).
- Success claims the application atomically; a retry is rejected.
- Router maps business-rule rejections to 409 and unknown ids to 404.
- Partial unique index: at most one completed row per application.

Uses the conftest sqlite test DB and conftest stub user 990003.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from core.security import require_auth
from database import get_session
from main import app
from models.db_models import (  # pyright: ignore[reportMissingImports]
    LinkedBankAccount,
    LoanApplication,
    LoanDisbursement,
    LoanOffer,
)
from services.loan_marketplace_service import (
    DisbursementRejected,
    disburse_loan,
    link_bank_account,
)

_USER_ID = 990003


def _cleanup():
    with get_session() as session:
        app_ids = [a.id for a in session.query(LoanApplication.id).filter(LoanApplication.user_id == _USER_ID)]
        offer_ids = [
            a.loan_offer_id
            for a in session.query(LoanApplication.loan_offer_id).filter(LoanApplication.user_id == _USER_ID)
        ]
        session.query(LoanDisbursement).filter(LoanDisbursement.user_id == _USER_ID).delete(
            synchronize_session=False
        )
        if app_ids:
            session.query(LoanApplication).filter(LoanApplication.id.in_(app_ids)).delete(
                synchronize_session=False
            )
        if offer_ids:
            session.query(LoanOffer).filter(
                LoanOffer.id.in_(offer_ids), LoanOffer.nbfc_name == "GH-670 Test NBFC"
            ).delete(synchronize_session=False)
        session.query(LinkedBankAccount).filter(LinkedBankAccount.user_id == _USER_ID).delete(
            synchronize_session=False
        )
        session.commit()


@pytest.fixture
def approved_app_id():
    _cleanup()
    with get_session() as session:
        offer = LoanOffer(
            nbfc_name="GH-670 Test NBFC",
            loan_type="personal",
            min_amount=10_000,
            max_amount=10_00_000,
            interest_rate_pct=12.0,
            min_tenure_months=6,
            max_tenure_months=60,
            min_credit_score=600,
            processing_fee_pct=1.0,
            is_active=True,
        )
        session.add(offer)
        session.flush()
        application = LoanApplication(
            user_id=_USER_ID,
            loan_offer_id=offer.id,
            requested_amount=1_00_000,
            requested_tenure_months=12,
            status="approved",
        )
        session.add(application)
        session.commit()
        app_id = int(application.id)  # type: ignore[arg-type]
    yield app_id
    _cleanup()


@pytest.fixture
def as_test_user():
    app.dependency_overrides[require_auth] = lambda: _USER_ID
    yield
    app.dependency_overrides.pop(require_auth, None)


def _rows(app_id, status=None):
    with get_session() as session:
        q = session.query(LoanDisbursement).filter(LoanDisbursement.loan_application_id == app_id)
        if status:
            q = q.filter(LoanDisbursement.status == status)
        return q.count()


def _app_status(app_id):
    with get_session() as session:
        return session.query(LoanApplication.status).filter(LoanApplication.id == app_id).scalar()


def test_no_primary_account_rejects_without_row(approved_app_id):
    for _ in range(3):
        with pytest.raises(DisbursementRejected):
            disburse_loan(approved_app_id, _USER_ID)
    assert _rows(approved_app_id) == 0
    assert _app_status(approved_app_id) == "approved"


def test_success_then_retry_rejected(approved_app_id):
    link_bank_account(_USER_ID, "Test Bank", "XXXX6700")

    first = disburse_loan(approved_app_id, _USER_ID)
    assert str(first.status) == "completed"
    assert _app_status(approved_app_id) == "disbursed"

    with pytest.raises(DisbursementRejected):
        disburse_loan(approved_app_id, _USER_ID)
    assert _rows(approved_app_id, "completed") == 1
    assert _rows(approved_app_id) == 1


def test_router_maps_409_and_404(client, approved_app_id, as_test_user):
    resp = client.post(f"/api/finance/loan-applications/{approved_app_id}/disburse")
    assert resp.status_code == 409, resp.text
    assert "bank account" in resp.json()["detail"]
    assert _rows(approved_app_id) == 0

    resp = client.post("/api/finance/loan-applications/987654321/disburse")
    assert resp.status_code == 404, resp.text


def test_unique_index_blocks_second_completed_row(approved_app_id):
    def _completed_row():
        return LoanDisbursement(
            loan_application_id=approved_app_id,
            user_id=_USER_ID,
            nbfc_name="GH-670 Test NBFC",
            disbursed_amount=1_00_000,
            status="completed",
            disbursed_at=datetime.now(timezone.utc),
        )

    with get_session() as session:
        session.add(_completed_row())
        session.commit()
        # A legacy failed row is still allowed alongside it.
        failed = _completed_row()
        failed.status = "failed"  # type: ignore[assignment]
        session.add(failed)
        session.commit()

        session.add(_completed_row())
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
