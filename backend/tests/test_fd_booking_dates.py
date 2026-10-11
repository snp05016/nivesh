"""MATH-21: FD maturity dates use calendar months, and the senior-citizen bonus
is applied (and locked on the booking) when the booker declares it."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest


@pytest.fixture
def fd_env(monkeypatch):
    """A throwaway user + 7.25% scheme (0.50 senior bonus, 1-120 months), KYC gate passing."""
    import database
    import services.fixed_deposit_service as fds
    from models.db_models import AuditLogEntry, FixedDepositScheme, User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    monkeypatch.setattr(fds, "_check_kyc_gate", lambda _uid, _dev: (True, "test gate"))
    with database.get_session() as session:
        user = User(username=f"fdd_{uuid4().hex[:12]}", password_hash="x", display_name="FD Dates")
        scheme = FixedDepositScheme(
            issuer_name=f"Date Bank {uuid4().hex[:8]}", min_tenure_months=1, max_tenure_months=120,
            min_amount=1_000, max_amount=10_00_000, interest_rate_pct=7.25,
            senior_citizen_bonus_pct=0.50, is_active=True,
        )
        session.add_all([user, scheme])
        session.commit()
        ids = (int(user.id), int(scheme.id))  # type: ignore[arg-type]
    yield ids
    with database.get_session() as session:
        row = session.get(FixedDepositScheme, ids[1])
        if row is not None:
            session.delete(row)  # ORM cascade removes the bookings
        # Audit rows (FINSEC-22) reference the user; drop them before the user.
        session.query(AuditLogEntry).filter(AuditLogEntry.user_id == ids[0]).delete(synchronize_session=False)
        user_row = session.get(User, ids[0])
        if user_row is not None:
            session.delete(user_row)
        session.commit()


def _freeze_now(monkeypatch, frozen: datetime):
    import services.fixed_deposit_service as fds

    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen

    monkeypatch.setattr(fds, "datetime", _Frozen)


def _book(user_id, scheme_id, tenure, senior=False):
    from services.fixed_deposit_service import book_fixed_deposit

    return book_fixed_deposit(
        user_id=user_id, scheme_id=scheme_id, principal_amount=1_00_000,
        tenure_months=tenure, payment_method="upi", device_id="dev", is_senior_citizen=senior,
    )


def test_24_month_fd_matures_on_same_calendar_date(fd_env, monkeypatch):
    _freeze_now(monkeypatch, datetime(2026, 10, 8, 10, 0, tzinfo=timezone.utc))
    booking = _book(*fd_env, tenure=24)
    assert booking.matures_at.date().isoformat() == "2028-10-08"  # was 2028-10-07 with 30.44-day months


def test_month_end_is_clamped(fd_env, monkeypatch):
    _freeze_now(monkeypatch, datetime(2026, 1, 31, 10, 0, tzinfo=timezone.utc))
    booking = _book(*fd_env, tenure=1)
    assert booking.matures_at.date().isoformat() == "2026-02-28"


def test_senior_citizen_bonus_is_applied_and_locked(fd_env):
    from services.fixed_deposit_service import calculate_fd_maturity

    regular = _book(*fd_env, tenure=12)
    senior = _book(*fd_env, tenure=12, senior=True)

    assert float(regular.interest_rate_pct) == pytest.approx(7.25)  # type: ignore[arg-type]
    assert float(senior.interest_rate_pct) == pytest.approx(7.75)  # type: ignore[arg-type]
    expected = calculate_fd_maturity(1_00_000, 12, 7.75)["maturity_amount"]
    assert float(senior.maturity_amount) == pytest.approx(expected)  # type: ignore[arg-type]
    assert float(senior.maturity_amount) > float(regular.maturity_amount)  # type: ignore[arg-type]
