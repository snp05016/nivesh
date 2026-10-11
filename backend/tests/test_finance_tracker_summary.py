"""FINSEC-29: Finance Tracker summary nets credit-card balances as liabilities,
and demo account linking is capped per user."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest


def _make_user() -> int:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"fin_summary_{uuid4().hex[:12]}", password_hash="x", display_name="Finance")
        session.add(user)
        session.commit()
        return user.id


def _add_account(user_id: int, account_type: str, balance: str) -> None:
    import database
    from models.db_models import FinanceTrackerAccount  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        session.add(
            FinanceTrackerAccount(
                user_id=user_id,
                bank_name="Test Bank",
                account_type=account_type,
                masked_account_number="XXXX0000",
                balance=Decimal(balance),
                last_synced_at=datetime.now(timezone.utc),
                is_mock=True,
            )
        )
        session.commit()


def _clear_accounts(user_id: int) -> None:
    import database
    from models.db_models import FinanceTrackerAccount  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        session.query(FinanceTrackerAccount).filter(FinanceTrackerAccount.user_id == user_id).delete()
        session.commit()


def test_credit_card_counts_as_liability():
    from services.finance_tracker_service import create_summary

    user_id = _make_user()
    try:
        _add_account(user_id, "savings", "100000.00")
        _add_account(user_id, "credit_card", "30000.00")

        summary = create_summary(user_id)

        assert summary["total_balance"] == pytest.approx(70000.0)
        assert summary["linked_account_count"] == 2
        # Mock income/spend scale off assets only (1,00,000), not the card balance.
        assert summary["monthly_income"] == pytest.approx(12000.0)
        assert summary["monthly_spend"] == pytest.approx(8000.0)
    finally:
        _clear_accounts(user_id)


def test_net_balance_can_be_negative_and_income_floors_at_zero():
    from services.finance_tracker_service import create_summary

    user_id = _make_user()
    try:
        _add_account(user_id, "credit_card", "25000.00")

        summary = create_summary(user_id)

        assert summary["total_balance"] == pytest.approx(-25000.0)
        assert summary["monthly_income"] == 0
        assert summary["monthly_spend"] == 0
    finally:
        _clear_accounts(user_id)


def test_demo_account_cap(client, auth_headers, test_user_id, monkeypatch):
    import config.settings
    from services.finance_tracker_service import MAX_DEMO_ACCOUNTS_PER_USER

    monkeypatch.setattr(config.settings, "DEMO_MODE", True)  # /api/finance is demo-gated (FAKE-23)
    _clear_accounts(test_user_id)
    try:
        payload = {"bank_name": "HDFC Bank", "account_type": "savings"}
        for _ in range(MAX_DEMO_ACCOUNTS_PER_USER):
            resp = client.post("/api/finance/accounts/link-demo", json=payload, headers=auth_headers)
            assert resp.status_code == 200, resp.text

        resp = client.post("/api/finance/accounts/link-demo", json=payload, headers=auth_headers)
        assert resp.status_code == 400
        assert "limit" in resp.json()["detail"]
    finally:
        _clear_accounts(test_user_id)
