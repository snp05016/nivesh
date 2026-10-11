"""Finance Tracker service — business logic + repository access for the
MOCK "linked account" balance/spend-tracking demo (Controller-Service-Repository).

routers/finance.py must only validate HTTP input and call functions here.
All session.query() calls for FinanceTrackerAccount live in this module.

MOCK DATA — simulated for demo purposes, not a real integration. No real
account-aggregator / bank-linking (OAuth/Plaid-style) flow is wired here;
balances, sync timestamps, and spend categories are all fabricated
server-side for demo purposes.

NOTE: This is functionally distinct from services/loan_marketplace_service.py's
LinkedBankAccount, which backs the Loan Marketplace (different shape/table).
"""
import hashlib
from datetime import datetime, timezone
from typing import Optional

from database import get_session
from models.db_models import FinanceTrackerAccount

VALID_ACCOUNT_TYPES = {"savings", "current", "credit_card", "wallet"}

# Fixed set of mock spend categories and their (deterministic) proportional
# share of monthly spend. MOCK DATA — not backed by real transaction
# categorization; percentages sum to 100.
_SPEND_CATEGORY_WEIGHTS = [
    ("Food", 0.28),
    ("Shopping", 0.22),
    ("Bills", 0.20),
    ("Transport", 0.12),
    ("Entertainment", 0.10),
    ("Other", 0.08),
]

# Deterministic mock multipliers used to derive monthly income/spend from a
# user's total linked balance. MOCK DATA — simulated for demo purposes, not
# a real income/spend feed.
_MOCK_MONTHLY_INCOME_RATIO = 0.12
_MOCK_MONTHLY_SPEND_RATIO = 0.08

# Credit-card balances are amounts owed (liabilities), not assets.
_LIABILITY_ACCOUNT_TYPES = {"credit_card"}

# Per-user cap on fabricated demo accounts (keeps the mock table bounded).
MAX_DEMO_ACCOUNTS_PER_USER = 10


def list_accounts(user_id: int) -> list[FinanceTrackerAccount]:
    """List the caller's MOCK Finance Tracker linked accounts."""
    with get_session() as session:
        return (
            session.query(FinanceTrackerAccount)
            .filter(FinanceTrackerAccount.user_id == user_id)
            .order_by(FinanceTrackerAccount.created_at.asc())
            .all()
        )


def create_summary(user_id: int) -> dict:
    """Aggregate balance summary across the caller's MOCK linked accounts.

    total_balance / linked_account_count are derived from real rows in
    finance_tracker_accounts. total_balance is a NET figure: credit_card
    balances are owed, so they are subtracted (the result may be negative).
    monthly_income / monthly_spend are MOCK DATA — simulated for demo
    purposes, not a real integration — deterministic figures scaled off
    the asset (non-credit-card) balance, not real transaction aggregation.
    """
    with get_session() as session:
        accounts = (
            session.query(FinanceTrackerAccount)
            .filter(FinanceTrackerAccount.user_id == user_id)
            .all()
        )
        assets = sum(float(a.balance) for a in accounts if a.account_type not in _LIABILITY_ACCOUNT_TYPES)
        liabilities = sum(float(a.balance) for a in accounts if a.account_type in _LIABILITY_ACCOUNT_TYPES)
        total_balance = assets - liabilities
        count = len(accounts)

    # MOCK DATA - simulated for demo purposes, not a real integration.
    income_base = max(assets, 0.0)
    monthly_income = round(income_base * _MOCK_MONTHLY_INCOME_RATIO, 2)
    monthly_spend = round(income_base * _MOCK_MONTHLY_SPEND_RATIO, 2)

    return {
        "total_balance": round(total_balance, 2),
        "linked_account_count": count,
        "monthly_income": monthly_income,
        "monthly_spend": monthly_spend,
    }


def list_spend_categories(user_id: int) -> list[dict]:
    """MOCK proportional spend-by-category breakdown derived from the
    user's monthly_spend summary figure.

    MOCK DATA — simulated for demo purposes, not a real integration. Not
    backed by real transaction categorization ML — just a fixed
    proportional split across a handful of common categories.
    """
    summary = create_summary(user_id)
    monthly_spend = summary["monthly_spend"]

    categories = []
    for category, weight in _SPEND_CATEGORY_WEIGHTS:
        categories.append(
            {
                "category": category,
                "amount": round(monthly_spend * weight, 2),
                "percentage": round(weight * 100, 2),
            }
        )
    return categories


def _fabricate_masked_account_number(user_id: int, bank_name: str, account_type: str, salt: int) -> str:
    """Deterministic-but-plausible-looking masked account number.
    MOCK DATA — simulated for demo purposes, not a real account number.
    """
    digest = hashlib.sha256(f"{user_id}:{bank_name}:{account_type}:{salt}".encode()).hexdigest()
    last4 = "".join(ch for ch in digest if ch.isdigit())[:4].rjust(4, "7")
    return f"XXXX{last4}"


def _fabricate_balance(user_id: int, bank_name: str, account_type: str, salt: int) -> float:
    """Deterministic-but-plausible-looking opening balance.
    MOCK DATA — simulated for demo purposes, not a real balance feed.
    """
    digest = hashlib.sha256(f"balance:{user_id}:{bank_name}:{account_type}:{salt}".encode()).hexdigest()
    magnitude = int(digest[:6], 16) % 500_000  # up to ~5 Lakh
    base = 5_000 if account_type == "credit_card" else 10_000
    return float(base + magnitude)


def link_demo_account(user_id: int, bank_name: str, account_type: str) -> FinanceTrackerAccount:
    """Fabricate and persist a new MOCK "linked" Finance Tracker account.

    MOCK DATA — simulated for demo purposes, not a real integration. No
    real bank OAuth/Plaid-style linking flow happens here.
    """
    if account_type not in VALID_ACCOUNT_TYPES:
        raise ValueError(f"account_type must be one of {sorted(VALID_ACCOUNT_TYPES)}")

    with get_session() as session:
        salt = (
            session.query(FinanceTrackerAccount)
            .filter(FinanceTrackerAccount.user_id == user_id)
            .count()
        )
        if salt >= MAX_DEMO_ACCOUNTS_PER_USER:
            raise ValueError(f"demo account limit reached ({MAX_DEMO_ACCOUNTS_PER_USER} per user)")
        account = FinanceTrackerAccount(
            user_id=user_id,
            bank_name=bank_name,
            account_type=account_type,
            masked_account_number=_fabricate_masked_account_number(user_id, bank_name, account_type, salt),
            balance=_fabricate_balance(user_id, bank_name, account_type, salt),
            last_synced_at=datetime.now(timezone.utc),
            is_mock=True,
        )
        session.add(account)
        session.commit()
        session.refresh(account)
        return account
